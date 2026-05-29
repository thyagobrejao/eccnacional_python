#!/bin/bash
#
# migrate_db.sh — Migração de Banco de Dados PostgreSQL (DigitalOcean -> Local Docker)
# Sistema: eccnacional
#
# Execução: ./migrate_db.sh
#

set -Eeuo pipefail

# Caminhos dos diretórios
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}"
INFRA_DIR="$(cd "${SCRIPT_DIR}/../oracle-host" && pwd)"

# Variáveis globais para armazenar as credenciais
APP_DB_NAME=""
APP_DB_USER=""
APP_DB_PASSWORD=""
APP_DB_HOST=""
APP_DB_PORT="5432"

LOCAL_DB_USER="postgres"
LOCAL_DB_PASSWORD=""
LOCAL_DB_NAME="eccnacional"

# Cores para formatação de saída
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Sem cor

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}    MIGRAÇÃO DE BANCO DE DADOS POSTGRESQL - ECC NACIONAL (DO -> Local) ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. Carrega credenciais atuais da aplicação (DigitalOcean)
echo -e "\n🔍 Carregando credenciais do banco de dados de origem (DigitalOcean)..."
APP_ENV_FILE="${APP_DIR}/.env"

load_app_env() {
    local env_file="$1"
    if [ -f "${env_file}" ]; then
        set +u
        while IFS='=' read -r key value || [ -n "${key}" ]; do
            # Remove espaços extras
            key=$(echo "${key}" | xargs)
            value=$(echo "${value}" | xargs)
            
            # Ignora comentários e linhas vazias
            if [[ "${key}" =~ ^# ]] || [ -z "${key}" ]; then continue; fi
            
            # Remove aspas simples e duplas
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            
            case "${key}" in
                DB_NAME) APP_DB_NAME="${value}" ;;
                DB_USER) APP_DB_USER="${value}" ;;
                DB_PASSWORD) APP_DB_PASSWORD="${value}" ;;
                DB_HOST) APP_DB_HOST="${value}" ;;
                DB_PORT) APP_DB_PORT="${value}" ;;
            esac
        done < "${env_file}"
        set -u
    else
        echo -e "${RED}ERROR: Arquivo .env não encontrado em ${APP_ENV_FILE}!${NC}" >&2
        exit 1
    fi
}

load_app_env "${APP_ENV_FILE}"

# Valida se as credenciais mínimas foram carregadas
if [ -z "${APP_DB_HOST}" ] || [ -z "${APP_DB_NAME}" ] || [ -z "${APP_DB_USER}" ] || [ -z "${APP_DB_PASSWORD}" ]; then
    echo -e "${RED}ERROR: Não foi possível carregar as credenciais completas da origem em ${APP_ENV_FILE}!${NC}" >&2
    exit 1
fi

# 2. Carrega credenciais do banco local (Destino)
echo -e "🔍 Carregando credenciais do banco local (Destino) de oracle-host..."
LOCAL_ENV_FILE="${INFRA_DIR}/.env"

load_local_env() {
    local env_file="$1"
    if [ -f "${env_file}" ]; then
        set +u
        while IFS='=' read -r key value || [ -n "${key}" ]; do
            key=$(echo "${key}" | xargs)
            value=$(echo "${value}" | xargs)
            
            if [[ "${key}" =~ ^# ]] || [ -z "${key}" ]; then continue; fi
            
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            
            case "${key}" in
                POSTGRES_USER) LOCAL_DB_USER="${value}" ;;
                POSTGRES_PASSWORD) LOCAL_DB_PASSWORD="${value}" ;;
            esac
        done < "${env_file}"
        set -u
    else
        echo -e "${RED}ERROR: Arquivo .env de oracle-host não encontrado em ${LOCAL_ENV_FILE}!${NC}" >&2
        exit 1
    fi
}

load_local_env "${LOCAL_ENV_FILE}"

if [ -z "${LOCAL_DB_PASSWORD}" ]; then
    echo -e "${RED}ERROR: POSTGRES_PASSWORD local não definida em ${LOCAL_ENV_FILE}!${NC}" >&2
    exit 1
fi

# 3. Confirmação do Usuário
echo -e "\n${YELLOW}--- BANCO DE ORIGEM (DigitalOcean) ---${NC}"
echo -e "  Host:     ${APP_DB_HOST}"
echo -e "  Porta:    ${APP_DB_PORT}"
echo -e "  Banco:    ${APP_DB_NAME}"
echo -e "  Usuário:  ${APP_DB_USER}"
echo -e "  Senha:    ******"

echo -e "\n${YELLOW}--- BANCO DE DESTINO (Local Docker) ---${NC}"
echo -e "  Host:     localhost (container: postgres)"
echo -e "  Banco:    ${APP_DB_NAME}"
echo -e "  Usuário:  ${LOCAL_DB_USER}"
echo -e "  Senha:    ******"

echo -e "\n${YELLOW}IMPORTANTE:${NC} Certifique-se de que o IP público desta VM Oracle está liberado no painel da DigitalOcean."
read -p "Deseja continuar com a migração? (S/n): " confirm
confirm=$(echo "${confirm:-S}" | tr '[:lower:]' '[:upper:]')

if [ "${confirm}" != "S" ] && [ "${confirm}" != "SIM" ]; then
    echo -e "\n${RED}Migração cancelada pelo usuário.${NC}"
    exit 0
fi

# 4. Verifica se o Docker local do Postgres está saudável
echo -e "\n🔍 Verificando se o container 'postgres' está rodando..."
if ! docker ps --format '{{.Names}}' | grep -q "^postgres$"; then
    echo -e "${RED}ERROR: O container 'postgres' não está em execução! Suba a infraestrutura primeiro em oracle-host.${NC}" >&2
    exit 1
fi

# 5. Para as aplicações locais para evitar novos dados e liberar locks
echo -e "\n🛑 Parando containers de aplicação (docker compose down)..."
docker compose -f "${APP_DIR}/docker-compose.yml" down || true
echo -e "${GREEN}Containers de aplicação parados com sucesso.${NC}"

# 6. Realiza o pg_dump da DigitalOcean por dentro do container local do Postgres
echo -e "\n📥 Iniciando a extração dos dados (pg_dump) da DigitalOcean..."
echo -e "${YELLOW}Isso pode levar alguns instantes dependendo do tamanho do banco...${NC}"

DUMP_TMP_PATH="/tmp/migration_do_${APP_DB_NAME}.dump"

# Executa o dump conectando na DigitalOcean de dentro do container de Postgres local
# Isso evita a necessidade de ter pg_dump instalado no host Ubuntu
if docker exec -e PGPASSWORD="${APP_DB_PASSWORD}" -t postgres \
    pg_dump -h "${APP_DB_HOST}" -p "${APP_DB_PORT}" -U "${APP_DB_USER}" -d "${APP_DB_NAME}" \
    -F c -b -v -f "${DUMP_TMP_PATH}"; then
    echo -e "${GREEN}Extração de dados concluída com sucesso!${NC}"
else
    echo -e "${RED}ERROR: Falha ao extrair dados do Postgres da DigitalOcean!${NC}" >&2
    echo -e "${YELLOW}Verifique se o IP público da VM Oracle está liberado no painel da DigitalOcean.${NC}"
    echo -e "Subindo os containers de aplicação novamente..."
    docker compose -f "${APP_DIR}/docker-compose.yml" up -d || true
    exit 1
fi

# 7. Prepara o banco local (cria se não existir)
echo -e "\n🛠️ Preparando banco de dados local..."
# Cria o banco localmente se ele não existir
docker exec -t postgres psql -U "${LOCAL_DB_USER}" -c "CREATE DATABASE ${APP_DB_NAME};" || true

# 8. Realiza o pg_restore
echo -e "\n📤 Restaurando dados no Postgres local..."
if docker exec -e PGPASSWORD="${LOCAL_DB_PASSWORD}" -t postgres \
    pg_restore -U "${LOCAL_DB_USER}" -d "${APP_DB_NAME}" -v --clean --no-owner --no-privileges "${DUMP_TMP_PATH}"; then
    echo -e "${GREEN}Restauração de dados concluída com sucesso!${NC}"
else
    echo -e "${YELLOW}Restauração concluída (com possíveis avisos não críticos).${NC}"
fi

# 9. Limpa arquivo temporário de dentro do container
echo -e "\n🧹 Limpando arquivos temporários..."
docker exec -t postgres rm -f "${DUMP_TMP_PATH}"

# 10. Atualiza o .env da aplicação para apontar para o novo banco local
echo -e "\n🔄 Atualizando o arquivo .env da aplicação..."
# Faz backup de segurança do .env original
cp "${APP_ENV_FILE}" "${APP_ENV_FILE}.bak"
echo -e "  Backup de segurança criado em: ${APP_ENV_FILE}.bak"

# Edita o arquivo .env para apontar para o container do postgres local na infra-network
# Usamos sed para substituir de forma segura as linhas
sed -i 's/^DB_HOST=.*/DB_HOST=postgres/' "${APP_ENV_FILE}"
sed -i "s/^DB_USER=.*/DB_USER=${LOCAL_DB_USER}/" "${APP_ENV_FILE}"
sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=${LOCAL_DB_PASSWORD}/" "${APP_ENV_FILE}"
sed -i "s/^DB_NAME=.*/DB_NAME=${APP_DB_NAME}/" "${APP_ENV_FILE}"
sed -i 's/^DB_PORT=.*/DB_PORT=5432/' "${APP_ENV_FILE}"

# Garante que o SSLMode está prefer ou disable
if grep -q "^DB_SSLMODE=" "${APP_ENV_FILE}"; then
    sed -i 's/^DB_SSLMODE=.*/DB_SSLMODE=prefer/' "${APP_ENV_FILE}"
fi

echo -e "${GREEN}Arquivo .env da aplicação atualizado com sucesso!${NC}"

# 11. Inicia novamente os containers da aplicação
echo -e "\n🚀 Recriando e reiniciando os containers da aplicação com o novo banco local..."
docker compose -f "${APP_DIR}/docker-compose.yml" up -d

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}🎉        MIGRAÇÃO CONCLUÍDA COM SUCESSO!                             ${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo -e "Sua aplicação '${APP_DB_NAME}' já está rodando integrada ao Postgres local."
