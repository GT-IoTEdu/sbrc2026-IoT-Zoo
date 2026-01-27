# 🛡️ IoT-IDS Testbed: Ambiente de Simulação Heterogêneo

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/platform-linux--sudo-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

Este repositório contém a implementação de um **testbed IoT reprodutível** baseado em **Mininet-WiFi / Containernet**. O projeto simula um "Zoológico IoT" (*IoT Zoo*) contendo dispositivos heterogêneos — desde sensores médicos e industriais até câmeras de vigilância e estações meteorológicas — operando simultaneamente em containers Docker.

> **Objetivo:** Gerar tráfego de rede realista e datasets rotulados para o treinamento e validação de **Sistemas de Detecção de Intrusão (IDS)** em cenários de IoT/IIoT.

---

## 📋 Pré-requisitos

Para garantir a reprodução fiel dos experimentos, certifique-se de atender aos seguintes requisitos:

* 🐧 **Sistema Operacional:** Ubuntu 20.04 LTS ou 22.04 LTS (Máquina Virtual ou Física).
* 💻 **Hardware Recomendado:** Mínimo 4GB de RAM e 2 vCPUs.
* 🔑 **Permissões:** Acesso `root` (`sudo`) é obrigatório para o gerenciamento de interfaces de rede pelo Mininet.

---

## 🚀 Guia de Instalação (Passo a Passo)

### 1. Preparação do Sistema (Containernet)

Este projeto utiliza o Containernet, uma extensão do Mininet que permite usar containers Docker como hosts na topologia.

```bash
# 1. Atualize o sistema e instale ferramentas essenciais
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git ansible python3-pip

# 2. Instale o Containernet (Via Ansible - Método Recomendado)
git clone https://github.com/containernet/containernet.git
cd containernet/ansible
sudo ansible-playbook -i "localhost," -c local install.yml
cd ..
sudo make install

# 3. Instale dependências Python do orquestrador
sudo pip3 install docker pandas scikit-learn
```

### 2. Setup do Projeto IoT-IDS

Clone este repositório para sua máquina local:

```bash
cd ~
git clone https://github.com/GT-IoTEdu/Testbed-Virtual-02.git
cd Testbed-Virtual-02
```

### 3. Construção do Ambiente (Build)

Não é necessário configurar certificados ou containers manualmente. O script `build_images.sh` automatiza todo o processo:

1.  Ajusta permissões de execução.
2.  Gera uma **PKI** (Public Key Infrastructure) simulada para TLS.
3.  Constrói as **Imagens Docker** para cada sensor.

```bash
# Garante permissão de execução
chmod +x build_images.sh

# Inicia o build (Pode levar alguns minutos na primeira vez)
sudo ./build_images.sh
```

> ✅ **Sucesso:** Aguarde até ver a mensagem: `🎉 SUCESSO! O ambiente está pronto.`

---

## ▶️ Executando o Experimento

O script `run_experiment.py` é o orquestrador principal. Ele levanta a topologia, configura o roteamento e inicia a captura de tráfego.

### Sintaxe

```bash
sudo python3 run_experiment.py --time <segundos> --output <caminho_do_arquivo.pcap>
```

### Exemplos de Uso (Recomendado)

⚠️ **Nota:** Para evitar bloqueios de permissão do sistema (AppArmor) ao gravar arquivos de captura, recomendamos salvar o resultado na pasta `/tmp`.

**Teste Rápido (60 segundos):**
```bash
sudo python3 run_experiment.py --time 60 --output /tmp/capture_test.pcap
```

**Geração de Dataset Completo (10 minutos):**
```bash
sudo python3 run_experiment.py --time 600 --output /tmp/dataset_full.pcap
```

**Ao final, mova o arquivo gerado:**
```bash
mv /tmp/dataset_full.pcap ./meu_dataset.pcap
```

---

## 🏛️ Arquitetura do Cenário (IoT Zoo)

O ambiente simula quatro domínios distintos de IoT convivendo na mesma rede:

| Domínio | Dispositivo | Protocolo | Descrição |
| :--- | :--- | :--- | :--- |
| **e-Health** | `patient1` (mHealth) | MQTT | Simula sinais vitais. Código complexo com simulação de *drift* de tempo e reconexão. |
| **Indústria 4.0** | `cooler_motor` | MQTT | Sensor de vibração industrial. Envia payloads binários em Base64. |
| **Indústria 4.0** | `predictive` | MQTT (JSON) | Sensor de manutenção preditiva monitorando status de máquinas. |
| **Smart City** | `gw_co`, `gw_pm10`... | MQTT | 10 Gateways ambientais monitorando poluição com dados reais. |
| **Smart Home** | `domotic` | MQTT | Automação predial. Mistura formatos legados (XML) e modernos (JSON). |
| **Multimídia** | `ip_camera` | RTSP/UDP | Câmera IP transmitindo vídeo em tempo real. |

### Topologia de Rede
O experimento utiliza uma topologia em estrela gerenciada pelo Mininet, onde todos os dispositivos se comunicam através de um switch virtual (`s1`) conectado a um **Broker MQTT Central** (`10.0.0.100`) e um **Servidor de Vídeo** (`10.0.0.20`).

---

## 🔍 Analisando os Resultados

Abra o arquivo `.pcap` gerado no **Wireshark** para validar o tráfego:

1.  **Filtro MQTT (`tcp.port == 1883`):**
    * Observe a diversidade de tópicos: `hospital/patients`, `vibration/cooler`, etc.
    * Note os diferentes formatos de payload (JSON, Binário, XML).

2.  **Filtro Vídeo (`udp` ou `rtsp`):**
    * Verifique o fluxo contínuo de pacotes UDP entre a Câmera (`.21`) e o Servidor (`.20`).

---

## 🛠️ Detalhes de Implementação

### Estrutura de Diretórios
* `devices/`: Código-fonte e `Dockerfiles` de cada sensor.
* `devices/certificates/`: (Gerado no build) CA e certificados TLS.
* `build_images.sh`: Script mestre de automação.
* `run_experiment.py`: Orquestrador Python/Mininet.

---

## ❓ Solução de Problemas Comuns

<details>
<summary><strong>Clique para ver Soluções de Erros</strong></summary>

### Erro: `tcpdump: permission denied` ou arquivo com 0 bytes
* **Causa:** O AppArmor do Ubuntu bloqueia o tcpdump de escrever na pasta `/home`.
* **Solução:** Salve o output em `/tmp/` (ex: `--output /tmp/teste.pcap`) e depois mova o arquivo.

### Erro: `RTNETLINK answers: File exists`
* **Causa:** Uma execução anterior foi interrompida abruptamente e deixou interfaces virtuais presas.
* **Solução:** Execute o comando abaixo para limpar o Mininet:
    ```bash
    sudo mn -c
    ```
</details>

---

## 📜 Licença e Citação

Este projeto é open-source. Se você utilizá-lo em sua pesquisa, por favor cite:
> [Inserir aqui link para o paper]
