#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>

#define HOST "localhost"
#define PORT 8300
#define BUFFER_SIZE 4096
#define MAX_CODE_SIZE 2048

void error(const char *msg) {
    perror(msg);
    exit(1);
}

// Escapa a string para JSON (converte \n para \\n e " para \")
char* escape_code(const char* raw_code) {
    size_t raw_len = strlen(raw_code);
    size_t escaped_len = raw_len * 2 + 1; // Máximo de espaço necessário
    char* escaped = (char*)malloc(escaped_len);
    if (!escaped) error("malloc failed");

    char* dst = escaped;
    const char* src = raw_code;

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

// Conecta e envia a requisição
int main(int argc, char *argv[]) {
    int sockfd, n;
    struct sockaddr_in serv_addr;
    struct hostent *server;

    FILE *code_file;
    char raw_code[MAX_CODE_SIZE];
    char payload_buffer[BUFFER_SIZE];
    char response_buffer[BUFFER_SIZE];

    // 1. Abrir e Ler o Código Go
    const char *filename = "main.go";
    code_file = fopen(filename, "r");
    if (code_file == NULL) {
        fprintf(stderr, "ERRO: Não foi possível abrir o arquivo de código Go: %s\n", filename);
        exit(1);
    }

    size_t code_read = fread(raw_code, 1, MAX_CODE_SIZE - 1, code_file);
    raw_code[code_read] = '\0';
    fclose(code_file);

    // 2. Escapar o código para JSON
    char* escaped_code = escape_code(raw_code);

    // 3. Montar a Payload JSON
    // Formato esperado pelo servidor C: {"code": "...\n..."}\n
    snprintf(payload_buffer, sizeof(payload_buffer) - 1,
             "{\"code\":\"%s\"}\n", escaped_code);

    free(escaped_code);

    // 4. Configuração do Socket
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) error("ERROR opening socket");

    server = gethostbyname(HOST);
    if (server == NULL) {
        fprintf(stderr,"ERROR, no such host: %s\n", HOST);
        exit(1);
    }

    bzero((char *) &serv_addr, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    bcopy((char *)server->h_addr, (char *)&serv_addr.sin_addr.s_addr, server->h_length);
    serv_addr.sin_port = htons(PORT);

    // 5. Conectar
    printf("Conectando ao servidor em %s:%d...\n", HOST, PORT);
    if (connect(sockfd,(struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0)
        error("ERROR connecting");

    // 6. Enviar a Payload
    printf("Enviando código para execução remota (%zu bytes).\n", strlen(payload_buffer));
    n = write(sockfd, payload_buffer, strlen(payload_buffer));
    if (n < 0) error("ERROR writing to socket");

    // 7. Receber a Resposta
    printf("Aguardando resposta...\n");
    bzero(response_buffer, BUFFER_SIZE);

    // Lê a resposta em chunks até o fim ou buffer cheio
    int total_read = 0;
    while ((n = read(sockfd, response_buffer + total_read, BUFFER_SIZE - 1 - total_read)) > 0) {
        total_read += n;
        if (response_buffer[total_read - 1] == '\n' || total_read >= BUFFER_SIZE - 1) {
            break;
        }
    }
    if (n < 0) error("ERROR reading from socket");
    response_buffer[total_read] = '\0';

    // 8. Imprimir o Resultado
    printf("\n============== RESULTADO DO SERVIDOR ==============\n");
    printf("%s\n", response_buffer);
    printf("=================================================\n");

    close(sockfd);
    return 0;
}
