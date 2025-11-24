#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/wait.h> // Para a função waitpid() para evitar processos zumbis

/**
 * Função auxiliar para tratar erros.
 */
void error(const char *msg)
{
    perror(msg);
    exit(1);
}

/**
 * Função que lida com a comunicação com o cliente no processo filho.
 * @param newsockfd O descritor de socket da nova conexão aceita.
 */
void handle_client_process(int newsockfd)
{
    char buffer[256];
    int n;

    // 🚨 NOVO: Loop infinito para processar MÚLTIPLAS REQUISIÇÕES na mesma conexão
    while (1) {
        // 1. Comunicação (Read)
        bzero(buffer, 256);
        // Tenta ler a requisição (Bloqueia até receber dados ou a conexão fechar)
        n = read(newsockfd, buffer, 255);

        if (n < 0) {
            // Erro de leitura
            perror("ERROR reading from socket");
            break; // Sai do loop e fecha o socket
        }
        if (n == 0) {
            // Cliente fechou a conexão (EOF).
            // printf("Cliente desconectado (PID %d).\n", getpid()); // Opcional
            break; // Sai do loop e fecha o socket
        }

        // 2. Processamento/Log (opcional e lento)
        // printf("[PID %d] Message received: %s\n", getpid(), buffer);

        // 3. Comunicação (Write)
        // Envia a resposta de volta ao cliente
        n = write(newsockfd, "I got your message\n", 19);
        if (n < 0) {
            perror("ERROR writing to socket");
            break; // Sai do loop e fecha o socket
        }
    }

    // 4. Fechamento do Socket
    close(newsockfd);
    // O processo filho DEVE terminar após lidar com o cliente
    exit(0);
}


// --- Função principal do servidor ---

int main(int argc, char *argv[])
{
    int sockfd, newsockfd, portno;
    socklen_t clilen;
    struct sockaddr_in serv_addr, cli_addr;
    pid_t pid; // Variável para armazenar o ID do processo filho

    if (argc < 2) {
        fprintf(stderr, "ERROR, no port provided\n");
        exit(1);
    }

    // 1-5. Configuração e Bind do Socket
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0)
        error("ERROR opening socket");

    bzero((char *) &serv_addr, sizeof(serv_addr));
    portno = atoi(argv[1]);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(portno);

    if (bind(sockfd, (struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0)
        error("ERROR on binding");

    listen(sockfd, 1024); // Backlog aumentado

    printf("Server listening on port %d with processes (fork)...\n", portno);


    // 6. Loop Principal do Servidor (Não Finaliza)
    clilen = sizeof(cli_addr);
    while (1) {
        // --- 6.1 Accept (Bloqueia até nova conexão) ---
        newsockfd = accept(sockfd, (struct sockaddr *) &cli_addr, &clilen);
        if (newsockfd < 0) {
            perror("ERROR on accept");
            continue; // Continua o loop para aceitar novas conexões
        }

        // printf("[PID %d] Connection accepted. Creating child process.\n", getpid()); // Opcional

        // --- 6.2 Fork (Cria um novo processo para lidar com a requisição) ---
        pid = fork();

        if (pid < 0) {
            // Erro no fork
            error("ERROR on fork");
        }

        if (pid == 0) {
            // --- CÓDIGO DO PROCESSO FILHO ---
            close(sockfd); // O filho não precisa do socket de escuta principal
            handle_client_process(newsockfd); // Processa em loop
            // O exit(0) está dentro de handle_client_process
        } else {
            // --- CÓDIGO DO PROCESSO PAI ---
            close(newsockfd); // O pai fecha a cópia do socket de conexão

            // Reaping Zombies (Evita processos 'zumbis')
            // O WNOHANG garante que o pai não bloqueie
            while (waitpid(-1, NULL, WNOHANG) > 0);
        }
    }

    // Código inalcançável
    close(sockfd);
    return 0;
}
