// Publicador genérico DDS-XRCE dirigido por dataset para o IoT-Zoo.
//
// Reaproveita o padrão de sessão/transporte UDP dos clientes Micro-XRCE-DDS
// (mesma stack usada pelos atacantes do repositório `ataques`), porém em vez de
// floodar entidades, cria UMA cadeia participant -> topic -> publisher ->
// datawriter e publica cada linha do dataset CSV como uma amostra string,
// respeitando um intervalo de sleep configurável. Ao chegar no fim do arquivo,
// recomeça do início (comportamento equivalente ao readloop() do client.py).
//
// Uso:
//   client_xrce <agent_ip> <agent_port> <topic> <dataset_csv> <sleep_seconds>
//
// Compilação: ver compile.sh
//   gcc client_xrce.c -o client_xrce -lmicroxrcedds_client -lmicrocdr -lpthread

#include <uxr/client/client.h>
#include <ucdr/microcdr.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

#define STREAM_HISTORY 8
#define BUFFER_SIZE    (UXR_CONFIG_UDP_TRANSPORT_MTU * STREAM_HISTORY)
#define MAX_LINE       4096

// Lê a próxima linha "útil" do dataset, reabrindo o arquivo no EOF para repetir
// indefinidamente. Pula a primeira linha (cabeçalho CSV) a cada passada.
static int next_line(FILE** fp, const char* path, char* out, size_t out_sz)
{
    if (*fp == NULL) {
        *fp = fopen(path, "r");
        if (*fp == NULL) {
            return -1;
        }
        // descarta o cabeçalho
        if (fgets(out, (int)out_sz, *fp) == NULL) {
            return -1;
        }
    }

    if (fgets(out, (int)out_sz, *fp) == NULL) {
        // EOF: reabre e recomeça (pulando cabeçalho de novo)
        fclose(*fp);
        *fp = fopen(path, "r");
        if (*fp == NULL) {
            return -1;
        }
        if (fgets(out, (int)out_sz, *fp) == NULL) {       // cabeçalho
            return -1;
        }
        if (fgets(out, (int)out_sz, *fp) == NULL) {       // 1a linha de dados
            return -1;
        }
    }

    // remove o newline final
    out[strcspn(out, "\r\n")] = '\0';
    return 0;
}

int main(int argc, char** argv)
{
    if (argc != 6) {
        printf("Usage: %s <agent_ip> <agent_port> <topic> <dataset_csv> <sleep_seconds>\n",
               argv[0]);
        return 1;
    }

    const char* ip       = argv[1];
    const char* port      = argv[2];
    const char* topic_name = argv[3];
    const char* dataset    = argv[4];
    double sleep_seconds   = atof(argv[5]);

    printf("[xrce] agent=%s:%s topic=%s dataset=%s sleep=%.3fs\n",
           ip, port, topic_name, dataset, sleep_seconds);

    // --- Transporte UDP + sessão ---
    uxrUDPTransport transport;
    if (!uxr_init_udp_transport(&transport, UXR_IPv4, ip, port)) {
        printf("[xrce] ERROR: falha ao inicializar transporte UDP\n");
        return 1;
    }

    uxrSession session;
    uxr_init_session(&session, &transport.comm, 0xAABBCCDD);
    if (!uxr_create_session(&session)) {
        printf("[xrce] ERROR: falha ao criar sessao com o Agent\n");
        uxr_close_udp_transport(&transport);
        return 1;
    }

    uint8_t output_buffer[BUFFER_SIZE];
    uxrStreamId reliable_out =
        uxr_create_output_reliable_stream(&session, output_buffer, BUFFER_SIZE, STREAM_HISTORY);
    uint8_t input_buffer[BUFFER_SIZE];
    uxr_create_input_reliable_stream(&session, input_buffer, BUFFER_SIZE, STREAM_HISTORY);

    // --- Participant -> Topic -> Publisher -> DataWriter ---
    uxrObjectId participant_id = uxr_object_id(0x01, UXR_PARTICIPANT_ID);
    const char* participant_xml =
        "<dds><participant><rtps><name>iotzoo_participant</name></rtps></participant></dds>";
    uxr_buffer_create_participant_xml(&session, reliable_out, participant_id, 0,
                                      participant_xml, UXR_REPLACE);

    uxrObjectId topic_id = uxr_object_id(0x01, UXR_TOPIC_ID);
    char topic_xml[512];
    snprintf(topic_xml, sizeof(topic_xml),
             "<dds><topic><name>%s</name><dataType>std_msgs::msg::dds_::String_</dataType></topic></dds>",
             topic_name);
    uxr_buffer_create_topic_xml(&session, reliable_out, topic_id, participant_id,
                                topic_xml, UXR_REPLACE);

    uxrObjectId publisher_id = uxr_object_id(0x01, UXR_PUBLISHER_ID);
    uxr_buffer_create_publisher_xml(&session, reliable_out, publisher_id, participant_id,
                                    "", UXR_REPLACE);

    uxrObjectId datawriter_id = uxr_object_id(0x01, UXR_DATAWRITER_ID);
    char datawriter_xml[512];
    snprintf(datawriter_xml, sizeof(datawriter_xml),
             "<dds><data_writer><topic><kind>NO_KEY</kind><name>%s</name>"
             "<dataType>std_msgs::msg::dds_::String_</dataType></topic></data_writer></dds>",
             topic_name);
    uxr_buffer_create_datawriter_xml(&session, reliable_out, datawriter_id, publisher_id,
                                     datawriter_xml, UXR_REPLACE);

    if (!uxr_run_session_time(&session, 1000)) {
        printf("[xrce] WARN: confirmacao de criacao de entidades nao recebida (seguindo)\n");
    }

    // --- Loop de publicacao dirigido pelo dataset ---
    FILE* fp = NULL;
    char line[MAX_LINE];
    struct timespec ts;

    for (;;) {
        if (next_line(&fp, dataset, line, sizeof(line)) != 0) {
            printf("[xrce] ERROR: nao foi possivel ler o dataset `%s'\n", dataset);
            break;
        }

        // Serializa a linha CSV como uma string CDR e escreve no datawriter.
        ucdrBuffer mb;
        uint32_t topic_size = (uint32_t)(ucdr_alignment(0, 4) + 4 + strlen(line) + 1);
        if (uxr_prepare_output_stream(&session, reliable_out, datawriter_id, &mb, topic_size)) {
            ucdr_serialize_string(&mb, line);
            printf("[xrce] -> %s : %.80s\n", topic_name, line);
        } else {
            printf("[xrce] WARN: stream de saida sem espaco, pulando amostra\n");
        }

        uxr_run_session_time(&session, 100);

        if (sleep_seconds > 0) {
            ts.tv_sec  = (time_t)sleep_seconds;
            ts.tv_nsec = (long)((sleep_seconds - (double)ts.tv_sec) * 1e9);
            nanosleep(&ts, NULL);
        }
    }

    if (fp) {
        fclose(fp);
    }
    uxr_delete_session(&session);
    uxr_close_udp_transport(&transport);
    return 0;
}
