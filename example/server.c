#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>

/**
 * Função auxiliar para tratar erros.
 * Imprime a mensagem de erro no stderr e encerra o programa.
 */
void error(const char *msg)
{
    perror(msg);
    exit(1);
}

int main(int argc, char *argv[])
{
    // Variáveis para descritores de socket e número da porta
    int sockfd, newsockfd, portno;
    // Variável para armazenar o tamanho da estrutura de endereço do cliente
    socklen_t clilen;
    // Buffer para leitura e escrita de dados
    char buffer[256];
    // Estruturas de endereço para o servidor e o cliente
    struct sockaddr_in serv_addr, cli_addr;
    // Variável para armazenar o número de bytes lidos/escritos
    int n;

    // 1. Verificação de Argumentos (Porta)
    if (argc < 2) {
        fprintf(stderr, "ERROR, no port provided\n");
        exit(1);
    }

    // 2. Criação do Socket
    // AF_INET: domínio de endereço IPv4
    // SOCK_STREAM: tipo de socket TCP (orientado à conexão)
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0)
        error("ERROR opening socket");

    // Inicializa a estrutura do servidor com zeros
    bzero((char *) &serv_addr, sizeof(serv_addr));

    // Obtém o número da porta a partir dos argumentos da linha de comando
    portno = atoi(argv[1]);

    // 3. Configuração do Endereço do Servidor
    serv_addr.sin_family = AF_INET;
    // INADDR_ANY: aceita conexões de qualquer interface de rede
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    // htons: converte o número da porta para a ordem de bytes da rede
    serv_addr.sin_port = htons(portno);

    // 4. Bind (Associação do Socket ao Endereço e Porta)
    if (bind(sockfd, (struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0)
        error("ERROR on binding");

    // 5. Listen (Escuta por Conexões)
    // O 5 é o tamanho da fila de conexões pendentes (backlog)
    listen(sockfd, 5);

    // 6. Accept (Aceita a Primeira Conexão)
    clilen = sizeof(cli_addr);
    // Bloqueia até que um cliente se conecte
    newsockfd = accept(sockfd, (struct sockaddr *) &cli_addr, &clilen);
    if (newsockfd < 0)
        error("ERROR on accept");


    // 7. Comunicação (Read)
    bzero(buffer, 256);
    // Lê a mensagem do cliente (no máximo 255 bytes)
    n = read(newsockfd, buffer, 255);
    if (n < 0)
        error("ERROR reading from socket");

    // Imprime a mensagem recebida
    printf("Here is the message: %s\n", buffer);

    // 8. Comunicação (Write)
    // Envia a resposta de volta ao cliente
    n = write(newsockfd, "I got your message", 18);
    if (n < 0)
        error("ERROR writing to socket");

    // 9. Fechamento dos Sockets
    close(newsockfd); // Fecha o socket da conexão específica
    close(sockfd);    // Fecha o socket de escuta principal

    return 0;
}
