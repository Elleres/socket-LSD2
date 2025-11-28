#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h> // Biblioteca para Threads (Pthreads)

// O número máximo de threads é limitado pelo sistema
#define MAX_THREADS 1000

/**
 * Função auxiliar para tratar erros.
 * Imprime a mensagem de erro no stderr e encerra o programa.
 */
void error(const char *msg)
{
    perror(msg);
    exit(1);
}

/**
 * Função que será executada por cada thread para lidar com o cliente.
 * Recebe o descritor de socket da nova conexão como argumento (void *).
 */
 /**
  * Função que será executada por cada thread para lidar com o cliente.
  * AGORA EM LOOP PARA PROCESSAR MÚLTIPLAS REQUISIÇÕES
  */
 void *handle_client(void *socket_desc)
 {
     int newsockfd = *(int *)socket_desc;
     char buffer[256];
     int n;

     // A thread pode liberar o espaço de memória alocado para o socket_desc
     free(socket_desc);

     //  NOVO: Loop infinito para processar múltiplas requisições
     while (1) {
         // 1. Comunicação (Read)
         bzero(buffer, 256);
         // Tenta ler a requisição (Bloqueia até receber dados ou a conexão fechar)
         n = read(newsockfd, buffer, 255);

         if (n < 0) {
             // Erro de leitura.
             perror("ERROR reading from socket");
             break; // Sai do loop e fecha o socket
         }
         if (n == 0) {
             // Cliente fechou a conexão (EOF).
             // printf("Cliente desconectado.\n"); // Opcional
             break; // Sai do loop e fecha o socket
         }

         // 2. Processamento/Log (opcional e lento)
         // printf("[Thread ID %lu] Message received: %s\n", (unsigned long)pthread_self(), buffer);

         // 3. Comunicação (Write)
         // Envia a resposta de volta ao cliente (o que garante o Req/s)
         n = write(newsockfd, "I got your message\n", 19);
         if (n < 0) {
             perror("ERROR writing to socket");
             break; // Sai do loop e fecha o socket
         }
     }

     // 4. Fechamento do Socket
     close(newsockfd);

     // A thread termina sua execução
     pthread_exit(NULL);
 }

// --- Função principal do servidor ---

int main(int argc, char *argv[])
{
    int sockfd, newsockfd, portno;
    socklen_t clilen;
    struct sockaddr_in serv_addr, cli_addr;

    if (argc < 2) {
        fprintf(stderr, "ERROR, no port provided\n");
        exit(1);
    }

    // ... (Configuração e Bind do Socket - Mesmos passos do código anterior) ...
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

    listen(sockfd, 1024); // Aumentei o backlog (fila de espera) para melhor teste de carga

    printf("Server listening on port %d with threads...\n", portno);


    // 6. Loop Principal do Servidor (Não Finaliza)
    clilen = sizeof(cli_addr);
    while (1) {
        // --- 6.1 Accept (Bloqueia até nova conexão) ---
        newsockfd = accept(sockfd, (struct sockaddr *) &cli_addr, &clilen);
        if (newsockfd < 0) {
            perror("ERROR on accept");
            continue; // Continua o loop para aceitar novas conexões
        }

        printf("[Main Thread] Connection accepted. Creating new thread...\n");

        // --- 6.2 Preparação para a Thread ---
        // Aloca espaço na heap para passar o descritor de socket para a thread.
        // É necessário alocar, pois a variável 'newsockfd' seria sobrescrita
        // na próxima iteração do loop, causando um problema de concorrência.
        int *new_sock = (int *)malloc(sizeof(int));
        if (new_sock == NULL) {
            perror("Failed to allocate memory for socket descriptor");
            close(newsockfd);
            continue;
        }
        *new_sock = newsockfd; // Armazena o descritor de socket alocado

        // --- 6.3 Criação da Thread ---
        pthread_t client_thread;
        // pthread_create( &thread_id, &atributos, função, argumento )
        if (pthread_create(&client_thread, NULL, handle_client, (void *)new_sock) < 0) {
            perror("Could not create thread");
            close(newsockfd);
            free(new_sock);
            continue;
        }

        // --- 6.4 Desanexar a Thread (Detaching) ---
        // Desanexar a thread faz com que seus recursos sejam liberados automaticamente
        // após a sua conclusão, sem a necessidade de uma chamada explícita a pthread_join()
        // (evitando assim o equivalente a processos "zumbis" no mundo das threads).
        pthread_detach(client_thread);
    }

    // Este código só seria alcançado se o loop while(1) fosse quebrado
    close(sockfd);
    return 0;
}
