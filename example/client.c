#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h> // Para a função gethostbyname

/**
 * Função auxiliar para tratar erros.
 * Imprime a mensagem de erro no stderr e encerra o programa.
 */
void error(const char *msg)
{
    perror(msg);
    exit(0); // Nota: Em servidores e clientes simples, é comum usar exit(0) aqui, mas exit(1) é mais tradicional para indicar falha.
}

int main(int argc, char *argv[])
{
    // Descritor de socket, número da porta e bytes lidos
    int sockfd, portno, n;
    // Estrutura de endereço do servidor
    struct sockaddr_in serv_addr;
    // Estrutura para informações do host (nome do servidor)
    struct hostent *server;
    // Buffer para comunicação
    char buffer[256];

    // 1. Verificação de Argumentos (hostname e porta)
    if (argc < 3) {
        fprintf(stderr, "usage %s hostname port\n", argv[0]);
        exit(0);
    }

    // Converte o argumento da porta para inteiro
    portno = atoi(argv[2]);

    // 2. Criação do Socket (TCP)
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0)
        error("ERROR opening socket");

    // 3. Obtenção do Endereço do Servidor
    // Converte o nome do host (ex: "localhost" ou "google.com") para endereço IP
    server = gethostbyname(argv[1]);
    if (server == NULL) {
        fprintf(stderr, "ERROR, no such host\n");
        exit(0);
    }

    // Inicializa a estrutura do servidor com zeros
    bzero((char *) &serv_addr, sizeof(serv_addr));

    // Configuração do Endereço do Servidor
    serv_addr.sin_family = AF_INET;

    // Copia o endereço IP do host obtido para a estrutura de endereço
    bcopy((char *)server->h_addr,
         (char *)&serv_addr.sin_addr.s_addr,
         server->h_length);

    // Converte o número da porta para a ordem de bytes da rede
    serv_addr.sin_port = htons(portno);


    // 4. Conexão com o Servidor
    if (connect(sockfd, (struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0)
        error("ERROR connecting");

    // 5. Envio da Mensagem
    printf("Please enter the message: ");
    bzero(buffer, 256);
    // Lê a entrada do usuário
    fgets(buffer, 255, stdin);

    // Escreve a mensagem no socket para o servidor
    n = write(sockfd, buffer, strlen(buffer));
    if (n < 0)
        error("ERROR writing to socket");

    // 6. Recepção da Resposta
    bzero(buffer, 256);
    // Lê a resposta do servidor
    n = read(sockfd, buffer, 255);
    if (n < 0)
        error("ERROR reading from socket");

    // Imprime a resposta
    printf("%s\n", buffer);

    // 7. Fechamento do Socke
    close(sockfd);

    return 0;
}
