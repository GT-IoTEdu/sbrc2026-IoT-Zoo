FROM eclipse/zenoh:1.5.0

# --- CORREÇÃO PARA MININET/CONTAINERNET ---
# Instala bash (controle), iproute2/ethtool (rede) e iputils (ping).
# A imagem oficial do Zenoh é baseada em Alpine, então usamos 'apk'.
RUN apk add --no-cache bash iproute2 iputils ethtool

# A imagem oficial expõe o binário em /zenohd via ENTRYPOINT absoluto. Como
# removemos o ENTRYPOINT (o Mininet/run_experiment.py inicia o router com o
# comando `zenohd`), criamos um symlink para deixá-lo acessível no PATH.
RUN ln -sf /zenohd /usr/local/bin/zenohd

EXPOSE 7447 8000

# Remove o Entrypoint original (zenohd) para o Mininet assumir o controle.
# O router é iniciado manualmente pelo run_experiment.py.
ENTRYPOINT ["/bin/bash"]
CMD []
