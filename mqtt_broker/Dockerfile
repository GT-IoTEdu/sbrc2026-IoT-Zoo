FROM eclipse-mosquitto:1.6

# --- CORREÇÃO PARA MININET/CONTAINERNET ---
# Instala bash (controle), iproute2/ethtool (rede) e iputils (ping)
# O broker original é Alpine, então usamos 'apk' em vez de 'apt'
RUN apk add --no-cache bash iproute2 iputils ethtool

# Remove o Entrypoint original para o Mininet assumir o controle
ENTRYPOINT ["/bin/bash"]
CMD []
