import csv
import os
import socket
import statistics
import threading
import time
from typing import Any, Dict, List, Tuple

# --- Configurações do Teste ---
HOST = "127.0.0.1"
PORT = 8300
DURACAO_SEGUNDOS = 10
PAYLOAD = "TESTE DE CARGA\n"  # Deve terminar com '\n' para o servidor C
NUM_REPETICOES = 3  # Quantas vezes repetir cada nível de carga
CSV_FILENAME = "resultados_estresse_tcp_python.csv"

# Níveis de carga a serem testados (número de clientes simultâneos)
LISTA_CLIENTES = [2000, 5000, 8000, 9000]


# --- Variáveis de Contagem (Protegidas por Lock) ---
class Counters:
    def __init__(self):
        self.lock = threading.Lock()
        self.req_completas = 0
        self.conexoes_iniciadas = 0
        self.erros_conexao = 0
        self.erros_io_read = 0
        self.erros_io_write = 0

    def increment(self, counter_name: str):
        with self.lock:
            if counter_name == "req_completas":
                self.req_completas += 1
            elif counter_name == "conexoes_iniciadas":
                self.conexoes_iniciadas += 1
            elif counter_name == "erros_conexao":
                self.erros_conexao += 1
            elif counter_name == "erros_io_read":
                self.erros_io_read += 1
            elif counter_name == "erros_io_write":
                self.erros_io_write += 1


def client_task(stop_time: float, counters: Counters):
    """Simula um único cliente enviando requisições em loop."""
    # Aumentando o timeout para dar mais chance ao servidor (10s para conexão, 5s para I/O)
    CONNECTION_TIMEOUT = 10
    IO_TIMEOUT = 5

    try:
        # 1. Cria a Conexão
        conn = socket.create_connection((HOST, PORT), timeout=CONNECTION_TIMEOUT)
        conn.settimeout(IO_TIMEOUT)  # Timeout para operações de I/O

        counters.increment("conexoes_iniciadas")

        # 2. Loop de Requisições baseado em TEMPO
        while time.time() < stop_time:
            # Envia a string simples
            try:
                conn.sendall(PAYLOAD.encode("utf-8"))
            except socket.error:
                counters.increment("erros_io_write")
                break  # Sai do loop se a escrita falhar

            # Lê a resposta (USANDO LEITURA EFICIENTE)
            try:
                # Tenta ler um buffer de 256 bytes de uma vez para reduzir chamadas de sistema.
                # O servidor envia apenas 19 bytes, então isso é suficiente.
                data = conn.recv(256)

                # Requisicao bem-sucedida somente se a mensagem foi recebida e contém o terminador
                if data.endswith(b"\n"):
                    counters.increment("req_completas")
                elif not data:
                    # Conexão fechada pelo servidor (EOF)
                    counters.increment("erros_io_read")
                    break
                else:
                    # Recebeu dados, mas sem terminador esperado
                    counters.increment("erros_io_read")
                    break

            except socket.timeout:
                counters.increment("erros_io_read")
                break  # Sai do loop se o timeout de leitura for atingido
            except OSError:
                counters.increment("erros_io_read")
                break  # Sai do loop por erro de socket durante leitura

    except ConnectionRefusedError:
        counters.increment("erros_conexao")
    except socket.timeout:
        counters.increment("erros_conexao")  # Timeout na conexão inicial
    except OSError as e:
        if e.errno == 99:  # Cannot assign requested address (EADDRNOTAVAIL)
            counters.increment("erros_conexao")
        else:
            counters.increment(
                "erros_conexao"
            )  # Outros erros de rede na conexão inicial
    except Exception:
        counters.increment("erros_conexao")
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass  # A conexão nunca foi criada


def run_single_test_round(num_clientes: int) -> Dict[str, Any]:
    """Executa uma única rodada de teste com N clientes."""
    counters = Counters()
    threads: List[threading.Thread] = []

    start_time = time.time()
    stop_time = start_time + DURACAO_SEGUNDOS

    # 1. Cria e inicia todas as threads (Clientes)
    for _ in range(num_clientes):
        t = threading.Thread(target=client_task, args=(stop_time, counters))
        threads.append(t)
        t.start()

    # 2. Espera que todas as threads terminem
    for t in threads:
        t.join(timeout=DURACAO_SEGUNDOS + 5)

    end_time = time.time()
    total_time = end_time - start_time

    # 3. Calcula os Resultados
    taxa_media = 0.0
    if total_time > 0 and counters.req_completas > 0:
        taxa_media = counters.req_completas / total_time

    total_erros_io = counters.erros_io_read + counters.erros_io_write

    # 4. Retorna o Dicionário de Resultados
    return {
        "Clientes_Simultaneos": num_clientes,
        "Repeticao": 0,  # Placeholder
        "Req_Bem_Sucedidas": counters.req_completas,
        "Conexoes_Iniciadas": counters.conexoes_iniciadas,
        "Erros_Conexao_Inicial": counters.erros_conexao,
        "Erros_I_O_Read": counters.erros_io_read,
        "Erros_I_O_Write": counters.erros_io_write,
        "Total_Erros_I_O": total_erros_io,
        "Tempo_Execucao_s": total_time,
        "Taxa_Media_Req_s": taxa_media,
    }


def main():
    print("-" * 60)
    print(f"Iniciando Teste de Estresse TCP | Host: {HOST}:{PORT}")
    print(
        f"Duração por rodada: {DURACAO_SEGUNDOS}s | Repetições por carga: {NUM_REPETICOES}"
    )
    print("-" * 60)

    all_results: List[Dict[str, Any]] = []

    # NOVO: Variável para registrar o primeiro ponto de falha de conexão
    first_conn_fail_level: int = 0

    for num_clientes in LISTA_CLIENTES:
        print(f"\nTeste de Carga: {num_clientes} Clientes")

        # Variável local para acumular os erros de conexão nesta carga
        current_load_conn_errors: List[int] = []

        for i in range(1, NUM_REPETICOES + 1):
            print(f"  -> Repetição {i}/{NUM_REPETICOES}...")

            result = run_single_test_round(num_clientes)
            result["Repeticao"] = i
            all_results.append(result)
            current_load_conn_errors.append(result["Erros_Conexao_Inicial"])

            print(
                f"    - Sucesso: {result['Req_Bem_Sucedidas']} Req | Vazão: {result['Taxa_Media_Req_s']:.2f} req/s"
            )
            print(
                f"    - Erros: Conn={result['Erros_Conexao_Inicial']} | I/O Read={result['Erros_I_O_Read']} | I/O Write={result['Erros_I_O_Write']}"
            )

            time.sleep(2)

        # 🚨 Lógica para identificar a Primeira Falha de Conexão
        # Se o total de erros de conexão nesta carga for maior que zero E ainda não detectamos a falha
        if first_conn_fail_level == 0 and sum(current_load_conn_errors) > 0:
            first_conn_fail_level = num_clientes
            print("=========================================================")
            print(f"🚨 PONTO DE FALHA DE CONEXÃO DETECTADO PELA PRIMEIRA VEZ!")
            print(f"   Limite atingido no nível de carga: {num_clientes} Clientes.")
            print("=========================================================")

    save_data_to_csv(all_results)
    print_summary(all_results, first_conn_fail_level)

    print("-" * 60)
    print("✅ Teste de Estresse Concluído.")
    print(f"Resultados detalhados salvos em: {CSV_FILENAME}")
    print("-" * 60)


def save_data_to_csv(results: List[Dict[str, Any]]):
    """Salva a lista de resultados em um arquivo CSV."""
    if not results:
        return

    fieldnames = list(results[0].keys())

    try:
        with open(CSV_FILENAME, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
    except Exception as e:
        print(f"ERRO ao salvar CSV: {e}")


def print_summary(results: List[Dict[str, Any]], first_conn_fail_level: int):
    """Calcula e imprime um resumo da vazão média e erros por nível de clientes."""
    summary: Dict[int, Dict[str, List[float]]] = {}

    for res in results:
        clientes = res["Clientes_Simultaneos"]

        if clientes not in summary:
            summary[clientes] = {
                "taxas": [],
                "erros_conn": [],
                "erros_io": [],
                "sucesso": [],
            }

        summary[clientes]["taxas"].append(res["Taxa_Media_Req_s"])
        summary[clientes]["erros_conn"].append(res["Erros_Conexao_Inicial"])
        summary[clientes]["erros_io"].append(res["Total_Erros_I_O"])
        summary[clientes]["sucesso"].append(res["Req_Bem_Sucedidas"])

    print("\n" + "=" * 60)
    print("Resumo do Desempenho (Média por Nível de Carga)")
    print("=" * 60)

    if first_conn_fail_level > 0:
        print(
            f"**🚨 Primeira Falha de Conexão (Limite) Detectada em: {first_conn_fail_level} Clientes**"
        )
        print("-" * 60)

    print(
        f"{'Clientes':<10} | {'Vazão Média (Req/s)':<25} | {'Erros Conexão':<15} | {'Erros I/O':<15}"
    )
    print("-" * 60)

    for clientes, data in sorted(summary.items()):
        media_taxa = statistics.mean(data["taxas"])
        media_erros_conn = statistics.mean(data["erros_conn"])
        media_erros_io = statistics.mean(data["erros_io"])

        print(
            f"{clientes:<10} | {media_taxa:<25.2f} | {media_erros_conn:<15.1f} | {media_erros_io:<15.1f}"
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTeste interrompido pelo usuário.")
        exit(0)
    except Exception as e:
        print(f"\nERRO FATAL: {e}")
