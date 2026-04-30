import subprocess
import uuid
import datetime
import os

def start_rtmp_server(session_id=None):
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"video_{session_id}_{timestamp}.mp4"
    
    # Usamos o teu IP e a porta padrão RTMP (1935)
    # O FFmpeg vai ficar em modo 'listen' aguardando a conexão
    rtmp_url = "rtmp://10.222.248.231:1935/live/stream"
    
    print("-" * 30)
    print(f"SERVIDOR RTMP INICIADO")
    print(f"Endereço: {rtmp_url}")
    print(f"Gravação: {filename}")
    print("-" * 30)

    # Comando FFmpeg para escutar e salvar
    command = [
        'ffmpeg',
        '-listen', '1',        # Ativa o modo servidor
        '-i', rtmp_url,        # Entrada do stream
        '-c', 'copy',          # Copia o codec (sem uso de CPU extra)
        '-f', 'mp4',           # Formato de saída
        filename
    ]

    try:
        # Executa o comando e aguarda o stream começar e terminar
        subprocess.run(command, check=True)
        print(f"\nGravação concluída com sucesso: {filename}")
    except Exception as e:
        print(f"\nErro ou Conexão encerrada: {e}")

if __name__ == "__main__":
    # Mantém o servidor rodando em loop para novas gravações
    while True:
        try:
            start_rtmp_server()
        except KeyboardInterrupt:
            print("\nServidor desligado pelo utilizador.")
            break