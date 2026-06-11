FROM eclipse/zenoh:1.7.2

# --- CORREÇÃO PARA MININET/CONTAINERNET ---
# Instala bash (controle), iproute2/ethtool (rede) e iputils (ping).
# A imagem oficial do Zenoh é baseada em Alpine, então usamos 'apk'.
RUN apk add --no-cache bash iproute2 iputils ethtool

EXPOSE 7447 8000

# Remove o Entrypoint original (zenohd) para o Mininet assumir o controle.
# O router é iniciado manualmente pelo run_experiment.py.
ENTRYPOINT ["/bin/bash"]
CMD []
