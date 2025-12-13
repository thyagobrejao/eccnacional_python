"""
Management command para popular a tabela de cidades a partir da API do IBGE.

API utilizada: https://servicodados.ibge.gov.br/api/v1/localidades/municipios
"""

import json
import urllib.request
import urllib.error
from django.core.management.base import BaseCommand
from municipios.models import Cidade


class Command(BaseCommand):
    help = "Popula a tabela de cidades com dados da API do IBGE"

    IBGE_API_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

    def add_arguments(self, parser):
        parser.add_argument(
            "--uf",
            type=str,
            help="Sigla da UF para filtrar (ex: SP, RJ). Se não informado, busca todos os municípios.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove todas as cidades antes de importar.",
        )

    def handle(self, *args, **options):
        uf_filter = options.get("uf")
        clear = options.get("clear")

        if clear:
            self.stdout.write(
                self.style.WARNING("Removendo todas as cidades existentes...")
            )
            deleted_count, _ = Cidade.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"{deleted_count} cidades removidas."))

        self.stdout.write("Buscando municípios na API do IBGE...")

        try:
            request = urllib.request.Request(
                self.IBGE_API_URL, headers={"Accept-Encoding": "gzip, deflate"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()

                # Decompress if gzip encoded
                if response.info().get("Content-Encoding") == "gzip":
                    import gzip

                    data = gzip.decompress(data)

                municipios = json.loads(data.decode("utf-8"))
        except urllib.error.URLError as e:
            self.stdout.write(self.style.ERROR(f"Erro ao buscar dados da API: {e}"))
            return
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"Erro ao decodificar JSON: {e}"))
            return

        self.stdout.write(f"Total de municípios encontrados na API: {len(municipios)}")

        # Função auxiliar para extrair UF do município
        def get_uf(m):
            """Extrai a UF do município de forma segura."""
            # Tenta a estrutura padrão: microrregiao.mesorregiao.UF
            try:
                microrregiao = m.get("microrregiao")
                if microrregiao:
                    mesorregiao = microrregiao.get("mesorregiao")
                    if mesorregiao:
                        uf_data = mesorregiao.get("UF")
                        if uf_data:
                            return uf_data.get("sigla")
            except (KeyError, TypeError):
                pass

            # Tenta estrutura alternativa: regiao-imediata.regiao-intermediaria.UF
            try:
                regiao_imediata = m.get("regiao-imediata")
                if regiao_imediata:
                    regiao_intermediaria = regiao_imediata.get("regiao-intermediaria")
                    if regiao_intermediaria:
                        uf_data = regiao_intermediaria.get("UF")
                        if uf_data:
                            return uf_data.get("sigla")
            except (KeyError, TypeError):
                pass

            return None

        # Filtrar por UF se informado
        if uf_filter:
            uf_filter = uf_filter.upper()
            municipios = [m for m in municipios if get_uf(m) == uf_filter]
            self.stdout.write(
                f"Municípios filtrados por UF {uf_filter}: {len(municipios)}"
            )

        # Buscar cidades existentes para evitar duplicatas
        existing = set(Cidade.objects.values_list("nome", "uf"))
        self.stdout.write(f"Cidades já cadastradas: {len(existing)}")

        # Preparar cidades para inserção em batch
        cidades_to_create = []
        skipped = 0
        for m in municipios:
            nome = m.get("nome")
            uf = get_uf(m)

            if not nome or not uf:
                skipped += 1
                continue

            if (nome, uf) not in existing:
                cidades_to_create.append(Cidade(nome=nome, uf=uf))

        if cidades_to_create:
            Cidade.objects.bulk_create(cidades_to_create, batch_size=500)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(cidades_to_create)} novas cidades cadastradas!"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Nenhuma cidade nova para cadastrar."))

        total_cidades = Cidade.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Total de cidades no banco: {total_cidades}")
        )
