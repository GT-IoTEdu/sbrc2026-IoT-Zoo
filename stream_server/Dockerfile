# 1. Usamos a imagem oficial nova (MediaMTX)
FROM bluenviron/mediamtx:latest AS rtsp

# 2. Base Alpine (igual ao original)
FROM alpine

# --- CORREÇÃO PARA MININET ---
# Instala bash e ethtool para funcionar na rede virtual
RUN apk add --no-cache bash iproute2 iputils ethtool

# 3. Copia o binário da nova imagem
# (Nota: o nome mudou de 'rtsp-simple-server' para 'mediamtx')
COPY --from=rtsp /mediamtx /

# 4. Copia sua configuração antiga, mas renomeia para o padrão novo
# O servidor novo espera ler 'mediamtx.yml'
COPY rtsp-simple-server.yml /mediamtx.yml

# 5. Define o ponto de entrada (não usamos ENTRYPOINT para o Mininet poder controlar se precisar)
# Mas deixamos o comando padrão pronto
CMD [ "/mediamtx" ]
