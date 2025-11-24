#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <sys/stat.h>
#include <libgen.h>
#include <sys/wait.h>     // Para pclose()
#include <fcntl.h>        // Para mkstemp, se necessário (depende do sistema)

#define BUFFER_SIZE 4096
#define MAX_OUTPUT_SIZE 4000
#define TEMP_FILE_TEMPLATE "./go_exec_XXXXXX.go"


// --- Funções Auxiliares de String e Erro ---

void error(const char *msg) {
    perror(msg);
    exit(1);
}

/**
 * @brief Encontra e retorna o conteúdo do campo "code" da string JSON.
 * @param json_str A string JSON recebida.
 * @return Um ponteiro para a string de código Go alocada dinamicamente e desescapada.
 */
char* extract_code_content(const char* json_str) {
    const char* start_key = strstr(json_str, "\"code\":\"");
    if (!start_key) return NULL;

    start_key += 8; // Pula "\"code\":\""

    const char* end_quote = strstr(start_key, "\"}");
    if (!end_quote) return NULL;

    size_t len = end_quote - start_key;

    char* code = (char*)malloc(len + 1);
    if (!code) error("malloc failed");
    strncpy(code, start_key, len);
    code[len] = '\0';

    // Desescapa manualmente as novas linhas (\\n -> \n) e aspas (\")
    char* src = code;
    char* dst = code;
    while (*src) {
        if (*src == '\\' && *(src + 1) == 'n') {
            *dst++ = '\n';
            src += 2;
        } else if (*src == '\\' && *(src + 1) == '"') {
            *dst++ = '"';
            src += 2;
        } else if (*src == '"') {
             src++; // Ignora aspas soltas
        } else {
            *dst++ = *src++;
        }
    }
    *dst = '\0';
    return code;
}

/**
 * @brief Escapa a saída para ser inserida em uma string JSON.
 * @param raw_output A saída bruta do comando (stdout/stderr).
 * @return Saída alocada dinamicamente e escapada.
 */
char* escape_json_output(const char* raw_output) {
    size_t raw_len = strlen(raw_output);
    size_t escaped_len = raw_len * 2 + 1;
    char* escaped = (char*)malloc(escaped_len);
    if (!escaped) error("malloc failed");

    char* dst = escaped;
    const char* src = raw_output;

    while (*src) {
        if (*src == '\n') {
            *dst++ = '\\';
            *dst++ = 'n';
        } else if (*src == '"') {
            *dst++ = '\\';
            *dst++ = '"';
        } else {
            *dst++ = *src;
        }
        src++;
    }
    *dst = '\0';
    return escaped;
}

/**
 * @brief Envia a resposta JSON de volta ao cliente.
 */
void send_response(int newsockfd, const char* output, const char* error_msg) {
    char response_buffer[BUFFER_SIZE * 2];
    char *escaped_output = NULL;
    char *escaped_error = NULL;

    if (output) escaped_output = escape_json_output(output);
    if (error_msg) escaped_error = escape_json_output(error_msg);

    // Formato JSON: {"output": "...", "error": "..."}\n
    snprintf(response_buffer, sizeof(response_buffer),
             "{\"output\": \"%s\", \"error\": \"%s\"}\n",
             escaped_output ? escaped_output : "",
             escaped_error ? escaped_error : "");

    write(newsockfd, response_buffer, strlen(response_buffer));

    if (escaped_output) free(escaped_output);
    if (escaped_error) free(escaped_error);
}


// --- Handler da Thread (Executor de Código) ---

void *handle_client(void *socket_desc) {
    int newsockfd = *(int *)socket_desc;
    char buffer[BUFFER_SIZE];
    int n;

    // O nome do arquivo temporário precisa ser um array mutável
    char temp_file_name[] = TEMP_FILE_TEMPLATE;
    char command[512];
    char output_buffer[MAX_OUTPUT_SIZE];
    char* code_content = NULL;
    FILE *pipe = NULL;

    free(socket_desc); // Libera o ponteiro alocado pelo main

    // 1. Comunicação (Read)
    bzero(buffer, BUFFER_SIZE);
    n = read(newsockfd, buffer, BUFFER_SIZE - 1);

    if (n <= 0) {
        if (n < 0) perror("ERROR reading from socket");
        goto cleanup;
    }
    buffer[n] = '\0';

    // 2. Extrair o Código
    code_content = extract_code_content(buffer);

    if (!code_content) {
        send_response(newsockfd, "", "Erro: Requisição JSON inválida ou campo 'code' ausente.");
        goto cleanup;
    }

    // 3. Salvar o Código em Arquivo Temporário
    int fd = mkstemp(temp_file_name);
    if (fd == -1) {
        send_response(newsockfd, "", "Erro do servidor: Não foi possível criar o arquivo temporário.");
        goto cleanup;
    }
    close(fd); // Fechamos o descritor retornado, vamos usar fopen/remove

    FILE *temp_file = fopen(temp_file_name, "w");
    if (!temp_file) {
        send_response(newsockfd, "", "Erro do servidor: Falha ao abrir o arquivo para escrita.");
        goto cleanup;
    }
    fprintf(temp_file, "%s", code_content);
    fclose(temp_file);

    // 4. Executar o Código usando popen
    // go run [arquivo] 2>&1 (Redireciona stderr para stdout)
    snprintf(command, sizeof(command), "go run %s 2>&1", temp_file_name);

    pipe = popen(command, "r");
    if (!pipe) {
        send_response(newsockfd, "", "Erro do servidor: Falha ao executar popen().");
        goto cleanup;
    }

    // 5. Ler a Saída e o Erro
    output_buffer[0] = '\0';
    char line_buffer[256];

    while (fgets(line_buffer, sizeof(line_buffer), pipe) != NULL) {
        // Concatena a saída, verificando o limite do buffer
        if (strlen(output_buffer) + strlen(line_buffer) < MAX_OUTPUT_SIZE) {
             strcat(output_buffer, line_buffer);
        } else {
             strcat(output_buffer, "... (Output truncado)");
             break;
        }
    }

    int result_code = pclose(pipe); // Captura o código de retorno

    // 6. Enviar a Resposta
    if (result_code != 0) {
        // Erro de compilação ou execução
        send_response(newsockfd, "", output_buffer);
    } else {
        // Sucesso na execução
        send_response(newsockfd, output_buffer, "");
    }

cleanup:
    // 7. Limpeza Final
    if (code_content) free(code_content);
    remove(temp_file_name); // Deleta o arquivo temporário
    close(newsockfd);
    pthread_exit(NULL);
}


// --- Função principal do servidor (Listener TCP) ---

int main(int argc, char *argv[])
{
    int sockfd, newsockfd, portno;
    socklen_t clilen;
    struct sockaddr_in serv_addr, cli_addr;

    if (argc < 2) {
        fprintf(stderr, "ERROR, no port provided\n");
        exit(1);
    }

    // 1. Inicialização do Socket e Reuso de Endereço
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) error("ERROR opening socket");

    int optval = 1;
    setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval));

    bzero((char *) &serv_addr, sizeof(serv_addr));
    portno = atoi(argv[1]);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(portno);

    if (bind(sockfd, (struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0)
        error("ERROR on binding");

    listen(sockfd, 5);

    printf("Servidor C Executor em espera na porta %d (Threads)...\n", portno);


    clilen = sizeof(cli_addr);
    while (1) {
        // 2. Accept: Aceita a conexão (Bloqueia o main thread)
        newsockfd = accept(sockfd, (struct sockaddr *) &cli_addr, &clilen);
        if (newsockfd < 0) {
            perror("ERROR on accept");
            continue;
        }

        // 3. Criação da Thread (Concorrência)
        int *new_sock = (int *)malloc(sizeof(int));
        if (new_sock == NULL) {
            perror("Failed to allocate memory");
            close(newsockfd);
            continue;
        }
        *new_sock = newsockfd;

        pthread_t client_thread;
        if (pthread_create(&client_thread, NULL, handle_client, (void *)new_sock) < 0) {
            perror("Could not create thread");
            close(newsockfd);
            free(new_sock);
            continue;
        }

        // 4. Desanexar (Essencial para não ter que esperar explicitamente a thread)
        pthread_detach(client_thread);
    }

    close(sockfd);
    return 0;
}
