"""
Importa dados do sistema legado (gestao_ecc – Laravel/MySQL) para o Django.

Tabelas importadas (na ordem de dependência):
  1. nacional / regionais / diocesanos / setoriais / dirigentes  →  Unidade
  2. users / users ↔ nivel/fk_nivel                              →  User + UserUnidade
  3. materiais                                                    →  Material
  4. materiais_equipes + estoques                                 →  UnidadeMaterial
  5. dados_bancario                                               →  DadoBancario
  6. equipes                                                      →  Equipe
  7. casais                                                       →  Casal  (+ Paroquia/Cidade)
  8. encontros                                                    →  Encontro
  9. casais_equipes                                               →  CasalEncontro
 10. pedidos + pedidos_materiais                                  →  Pedido + PedidoMaterial

Uso:
    python manage.py import_legacy_data \\
        --host=127.0.0.1 --port=3306 \\
        --database=gestao_ecc \\
        --user=root --password=secret

Variáveis de ambiente alternativas:
    LEGACY_DB_HOST, LEGACY_DB_PORT, LEGACY_DB_NAME,
    LEGACY_DB_USER, LEGACY_DB_PASSWORD
"""

import os
import sys
from decimal import Decimal

import pymysql
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bancos.models import DadoBancario
from casais.models import Casal
from encontros.models import CasalEncontro, Encontro
from equipes.models import Equipe
from materiais.models import Material, UnidadeMaterial
from municipios.models import Cidade
from paroquias.models import Paroquia
from pedidos.models import Pedido, PedidoMaterial
from unidades.models import Unidade, UserUnidade

User = get_user_model()

BATCH_SIZE = 1000

# ── Mapeamento nivel (legado) → Unidade.Tipo ────────────────────────────
# No legado: 1-4 = Nacional, 5 = Regional, 6 = Diocesano, 7 = Setorial, 8 = Dirigente
NIVEL_TO_TIPO = {
    1: Unidade.Tipo.NACIONAL,
    2: Unidade.Tipo.NACIONAL,
    3: Unidade.Tipo.NACIONAL,
    4: Unidade.Tipo.NACIONAL,
    5: Unidade.Tipo.REGIONAL,
    6: Unidade.Tipo.DIOCESANO,
    7: Unidade.Tipo.SETORIAL,
    8: Unidade.Tipo.PAROQUIA,
}

# Mapeamento nivel → tabela de origem
NIVEL_TO_TABLE = {
    1: "nacional",
    2: "nacional",
    3: "nacional",
    4: "nacional",
    5: "regionais",
    6: "diocesanos",
    7: "setoriais",
    8: "dirigentes",
}

ALL_STEPS = [
    "unidades",
    "users",
    "materiais",
    "unidade_material",
    "bancos",
    "equipes",
    "casais",
    "encontros",
    "casal_encontro",
    "pedidos",
]


def _convert_bcrypt_hash(laravel_hash: str) -> str:
    """
    Laravel usa prefixo $2y$ no bcrypt. Django (via bcrypt) espera $2b$.
    """
    if laravel_hash and laravel_hash.startswith("$2y$"):
        return "bcrypt$" + laravel_hash.replace("$2y$", "$2b$", 1)
    if laravel_hash and laravel_hash.startswith("$2b$"):
        return "bcrypt$" + laravel_hash
    return laravel_hash or ""


class Command(BaseCommand):
    help = "Importa dados do sistema legado (gestao_ecc – Laravel/MySQL) para o Django"
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--host", default=os.environ.get("LEGACY_DB_HOST", "127.0.0.1"))
        parser.add_argument("--port", type=int, default=int(os.environ.get("LEGACY_DB_PORT", "3306")))
        parser.add_argument("--database", default=os.environ.get("LEGACY_DB_NAME", "gestao_ecc"))
        parser.add_argument("--user", default=os.environ.get("LEGACY_DB_USER", "root"))
        parser.add_argument("--password", default=os.environ.get("LEGACY_DB_PASSWORD", ""))
        parser.add_argument(
            "--skip",
            nargs="*",
            choices=ALL_STEPS,
            default=[],
            help="Pular etapas (ex: --skip users pedidos)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a importação sem gravar dados",
        )


    def handle(self, **options):
        self.dry_run = options["dry_run"]
        self.verbosity = options["verbosity"]

        try:
            self.conn = pymysql.connect(
                host=options["host"],
                port=options["port"],
                user=options["user"],
                password=options["password"],
                database=options["database"],
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
        except pymysql.Error as exc:
            raise CommandError(f"Erro ao conectar no MySQL: {exc}") from exc

        skip = set(options["skip"])

        # Mapas de IDs legado → objeto Django (preenchidos durante a importação)
        self.unidade_map = {}          # (tabela, id_legado) → Unidade
        self.user_map = {}             # id_legado → User
        self.material_map = {}         # id_legado → Material
        self.equipe_map = {}           # id_legado → Equipe
        self.casal_map = {}            # id_legado → Casal
        self.encontro_map = {}         # id_legado → Encontro
        self.pedido_map = {}           # id_legado → Pedido
        self.cidade_cache = {}         # (cidade, uf) → Cidade
        self.paroquia_cache = {}       # (nome, cidade_id, unidade_id) → Paroquia

        with self.conn:
            for step in ALL_STEPS:
                if step in skip:
                    self.stdout.write(f"  ⏭  Pulando {step}")
                    continue
                handler = getattr(self, f"_import_{step}")
                handler()

        if self.dry_run:
            self.stdout.write(self.style.WARNING("\n⚠  Dry-run: nenhum dado foi gravado."))
        else:
            self.stdout.write(self.style.SUCCESS("\n✔  Importação concluída!"))

    def _progress(self, label, current, total):
        """Exibe progresso inline na mesma linha (sempre visível)."""
        pct = (current * 100 // total) if total else 100
        sys.stdout.write(f"\r    {label}: {current}/{total} ({pct}%)")
        sys.stdout.flush()
        if current >= total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    # ─────────────────────────────────────────────────────────────────────
    # 1. Unidades (hierarquia: nacional → regionais → diocesanos → setoriais → dirigentes)
    # ─────────────────────────────────────────────────────────────────────
    def _import_unidades(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando unidades…"))
        with self.conn.cursor() as cur:
            self._import_nacional(cur)
            self._import_regionais(cur)
            self._import_diocesanos(cur)
            self._import_setoriais(cur)
            self._import_dirigentes(cur)

        total = len(self.unidade_map)
        self.stdout.write(f"  {total} unidades importadas")

    def _import_nacional(self, cur):
        cur.execute("SELECT id, nome, digito, vencimento, bloqueado FROM nacional WHERE deleted_at IS NULL")
        rows = cur.fetchall()
        for i, row in enumerate(rows, 1):
            self._create_unidade(
                table="nacional",
                legacy_id=row["id"],
                nome=row["nome"] or "Nacional",
                tipo=Unidade.Tipo.NACIONAL,
                digito=row.get("digito"),
                vencimento=row.get("vencimento") or 40,
                bloqueado=bool(row.get("bloqueado")),
                parent=None,
            )
            self._progress("Nacional", i, len(rows))

    def _import_regionais(self, cur):
        cur.execute(
            "SELECT id, nome, nacional_id, bloqueado FROM regionais WHERE deleted_at IS NULL"
        )
        rows = cur.fetchall()
        for i, row in enumerate(rows, 1):
            parent = self.unidade_map.get(("nacional", row["nacional_id"]))
            self._create_unidade(
                table="regionais",
                legacy_id=row["id"],
                nome=row["nome"] or f"Regional {row['id']}",
                tipo=Unidade.Tipo.REGIONAL,
                digito=None,
                vencimento=40,
                bloqueado=bool(row.get("bloqueado")),
                parent=parent,
            )
            self._progress("Regionais", i, len(rows))

    def _import_diocesanos(self, cur):
        cur.execute(
            "SELECT id, nome, regionais_id, digito, vencimento, bloqueado "
            "FROM diocesanos WHERE deleted_at IS NULL"
        )
        rows = cur.fetchall()
        for i, row in enumerate(rows, 1):
            parent = self.unidade_map.get(("regionais", row["regionais_id"]))
            self._create_unidade(
                table="diocesanos",
                legacy_id=row["id"],
                nome=row["nome"] or f"Diocesano {row['id']}",
                tipo=Unidade.Tipo.DIOCESANO,
                digito=row.get("digito"),
                vencimento=row.get("vencimento") or 40,
                bloqueado=bool(row.get("bloqueado")),
                parent=parent,
            )
            self._progress("Diocesanos", i, len(rows))

    def _import_setoriais(self, cur):
        cur.execute(
            "SELECT id, nome, diocesanos_id, digito, vencimento, bloqueado "
            "FROM setoriais WHERE deleted_at IS NULL"
        )
        rows = cur.fetchall()
        for i, row in enumerate(rows, 1):
            parent = self.unidade_map.get(("diocesanos", row["diocesanos_id"]))
            self._create_unidade(
                table="setoriais",
                legacy_id=row["id"],
                nome=row["nome"] or f"Setorial {row['id']}",
                tipo=Unidade.Tipo.SETORIAL,
                digito=row.get("digito"),
                vencimento=row.get("vencimento") or 40,
                bloqueado=bool(row.get("bloqueado")),
                parent=parent,
            )
            self._progress("Setoriais", i, len(rows))

    def _import_dirigentes(self, cur):
        cur.execute(
            "SELECT id, paroquia, cidade, estado, bairro, setoriais_id, digito, vencimento, bloqueado "
            "FROM dirigentes WHERE deleted_at IS NULL"
        )
        rows = cur.fetchall()
        for i, row in enumerate(rows, 1):
            parent = self.unidade_map.get(("setoriais", row["setoriais_id"]))
            nome = row["paroquia"] or f"Paróquia {row['id']}"
            self._create_unidade(
                table="dirigentes",
                legacy_id=row["id"],
                nome=nome,
                tipo=Unidade.Tipo.PAROQUIA,
                digito=row.get("digito"),
                vencimento=row.get("vencimento") or 40,
                bloqueado=bool(row.get("bloqueado")),
                parent=parent,
            )
            self._progress("Dirigentes/Paróquias", i, len(rows))

    def _create_unidade(self, *, table, legacy_id, nome, tipo, digito, vencimento, bloqueado, parent):
        if self.dry_run:
            self.unidade_map[(table, legacy_id)] = None
            return
        with transaction.atomic():
            obj, _ = Unidade.objects.update_or_create(
                nome=nome,
                tipo=tipo,
                parent=parent,
                defaults={
                    "digito": digito,
                    "vencimento": vencimento,
                    "bloqueado": bloqueado,
                },
            )
        self.unidade_map[(table, legacy_id)] = obj

    # ─────────────────────────────────────────────────────────────────────
    # 2. Users + UserUnidade
    # ─────────────────────────────────────────────────────────────────────
    def _import_users(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando usuários…"))

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, password, editor, nivel, fk_nivel, telefone "
                "FROM users WHERE deleted_at IS NULL ORDER BY id"
            )
            rows = cur.fetchall()

        self.stdout.write(f"    {len(rows)} registros lidos do MySQL")

        if self.dry_run:
            for row in rows:
                self.user_map[row["id"]] = None
            self.stdout.write(f"  {len(rows)} usuários (dry-run)")
            return

        # Pré-carregar e-mails existentes para evitar SELECT por registro
        existing_users = {u.email: u for u in User.objects.all().only("id", "email")}

        users_to_create = []
        users_to_update = []
        legacy_rows_by_email = {}
        skipped = 0

        for i, row in enumerate(rows, 1):
            email = (row["email"] or "").strip().lower()
            if not email:
                skipped += 1
                continue

            name = row["name"] or ""
            parts = name.split(" ", 1)
            first_name = (parts[0] if parts else "")[:30]
            last_name = (parts[1] if len(parts) > 1 else "")[:150]

            password = _convert_bcrypt_hash(row["password"] or "")

            legacy_rows_by_email[email] = row

            if email in existing_users:
                user = existing_users[email]
                user.username = email
                user.first_name = first_name
                user.last_name = last_name
                user.password = password
                user.is_active = True
                user.is_staff = bool(row.get("editor"))
                users_to_update.append(user)
            else:
                user = User(
                    email=email,
                    username=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                    is_active=True,
                    is_staff=bool(row.get("editor")),
                )
                users_to_create.append(user)

            self._progress("Preparando usuários", i, len(rows))

        # Gravar em lote
        if users_to_create:
            self.stdout.write(f"    Criando {len(users_to_create)} usuários novos…")
            with transaction.atomic():
                User.objects.bulk_create(users_to_create, batch_size=BATCH_SIZE)

        if users_to_update:
            self.stdout.write(f"    Atualizando {len(users_to_update)} usuários existentes…")
            with transaction.atomic():
                User.objects.bulk_update(
                    users_to_update,
                    ["username", "first_name", "last_name", "password", "is_active", "is_staff"],
                    batch_size=BATCH_SIZE,
                )

        # Recarregar todos os usuários para montar o mapa de IDs
        all_users = {u.email: u for u in User.objects.all().only("id", "email")}

        # Montar user_map (legacy_id → User) e preparar UserUnidade em lote
        user_unidade_pairs = []

        for i, row in enumerate(rows, 1):
            email = (row["email"] or "").strip().lower()
            if not email:
                continue
            user = all_users.get(email)
            if not user:
                continue

            self.user_map[row["id"]] = user

            nivel = row.get("nivel")
            fk_nivel = row.get("fk_nivel")
            if nivel and fk_nivel:
                table = NIVEL_TO_TABLE.get(nivel)
                if table:
                    unidade = self.unidade_map.get((table, fk_nivel))
                    if unidade:
                        user_unidade_pairs.append((user, unidade))

            self._progress("Mapeando vínculos", i, len(rows))

        # Gravar UserUnidade em lote
        if user_unidade_pairs:
            existing_uu = set(
                UserUnidade.objects.values_list("user_id", "unidade_id")
            )
            uu_to_create = [
                UserUnidade(user=user, unidade=unidade, status=True)
                for user, unidade in user_unidade_pairs
                if (user.id, unidade.id) not in existing_uu
            ]
            if uu_to_create:
                self.stdout.write(f"    Criando {len(uu_to_create)} vínculos usuário-unidade…")
                with transaction.atomic():
                    UserUnidade.objects.bulk_create(uu_to_create, batch_size=BATCH_SIZE)

        total = len(users_to_create) + len(users_to_update)
        self.stdout.write(f"  {total} usuários importados ({skipped} sem e-mail pulados)")

    # ─────────────────────────────────────────────────────────────────────
    # 3. Materiais
    # ─────────────────────────────────────────────────────────────────────
    def _import_materiais(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando materiais…"))

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, descricao FROM materiais WHERE deleted_at IS NULL ORDER BY id"
            )
            rows = cur.fetchall()

        if self.dry_run:
            for row in rows:
                self.material_map[row["id"]] = None
            self.stdout.write(f"  {len(rows)} materiais (dry-run)")
            return

        existing = {m.descricao: m for m in Material.objects.all()}
        to_create = []

        for i, row in enumerate(rows, 1):
            desc = row["descricao"] or f"Material {row['id']}"
            if desc in existing:
                self.material_map[row["id"]] = existing[desc]
            else:
                obj = Material(descricao=desc)
                to_create.append((row["id"], obj))
            self._progress("Materiais", i, len(rows))

        if to_create:
            objs = [o for _, o in to_create]
            with transaction.atomic():
                Material.objects.bulk_create(objs, batch_size=BATCH_SIZE)
            all_mats = {m.descricao: m for m in Material.objects.all()}
            for legacy_id, obj in to_create:
                self.material_map[legacy_id] = all_mats[obj.descricao]

        # Garantir mapa completo
        all_mats = {m.descricao: m for m in Material.objects.all()}
        for row in rows:
            desc = row["descricao"] or f"Material {row['id']}"
            if row["id"] not in self.material_map:
                self.material_map[row["id"]] = all_mats.get(desc)

        self.stdout.write(f"  {len(rows)} materiais importados")

    # ─────────────────────────────────────────────────────────────────────
    # 4. UnidadeMaterial (materiais_equipes + estoques)
    # ─────────────────────────────────────────────────────────────────────
    def _import_unidade_material(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando preços e estoques…"))
        count = 0
        normalized_negative_stock = 0

        with self.conn.cursor() as cur:
            # Importar preços de materiais_equipes
            cur.execute(
                "SELECT me.id, me.fk_nivel, me.nivel, me.materiais_id, me.valor "
                "FROM materiais_equipes me "
                "INNER JOIN materiais m ON m.id = me.materiais_id AND m.deleted_at IS NULL "
                "ORDER BY me.id"
            )
            preco_rows = cur.fetchall()
            self.stdout.write(f"    {len(preco_rows)} preços lidos do MySQL")
            preco_map = {}  # (unidade_key, material_id) → valor
            for index, row in enumerate(preco_rows, start=1):
                table = NIVEL_TO_TABLE.get(row["nivel"])
                if not table:
                    continue
                unidade = self.unidade_map.get((table, row["fk_nivel"]))
                material = self.material_map.get(row["materiais_id"])
                if not unidade or not material:
                    continue
                if self.dry_run:
                    count += 1
                    continue
                key = (unidade.id, material.id)
                preco_map[key] = row["valor"] or Decimal("0.00")
                self._progress("Mapeando preços", index, len(preco_rows))

            # Importar estoques
            estoque_map = {}  # (unidade_key, material_id) → quantidade
            try:
                cur.execute(
                    "SELECT e.id, e.materiais_id, e.quantidade, e.nivel, e.fk_nivel "
                    "FROM estoques e "
                    "INNER JOIN materiais m ON m.id = e.materiais_id AND m.deleted_at IS NULL "
                    "ORDER BY e.id"
                )
                estoque_rows = cur.fetchall()
                self.stdout.write(f"    {len(estoque_rows)} estoques lidos do MySQL")
                for index, row in enumerate(estoque_rows, start=1):
                    table = NIVEL_TO_TABLE.get(row.get("nivel"))
                    if not table:
                        continue
                    unidade = self.unidade_map.get((table, row["fk_nivel"]))
                    material = self.material_map.get(row["materiais_id"])
                    if not unidade or not material:
                        continue
                    if self.dry_run:
                        count += 1
                        continue
                    key = (unidade.id, material.id)
                    quantidade = row["quantidade"] or 0
                    if quantidade < 0:
                        normalized_negative_stock += 1
                        quantidade = 0
                    estoque_map[key] = quantidade
                    self._progress("Mapeando estoques", index, len(estoque_rows))
            except pymysql.Error:
                self.stdout.write(
                    self.style.WARNING("    ⚠ Tabela estoques não encontrada, pulando")
                )
                estoque_rows = []

            final_records = {}

            all_keys = set(preco_map.keys()) | set(estoque_map.keys())
            self.stdout.write(f"    {len(all_keys)} combinações unidade/material")
            for index, (uid, mid) in enumerate(all_keys, start=1):
                final_records[(uid, mid)] = {
                    "valor": preco_map.get((uid, mid), Decimal("0.00")),
                    "quantidade": estoque_map.get((uid, mid), 0),
                }
                self._progress("Consolidando preços/estoques", index, len(all_keys))

            regionais_ids = [
                unidade.id for (table, _legacy_id), unidade in self.unidade_map.items() if unidade and table == "regionais"
            ]
            diocesanos_ids = [
                unidade.id for (table, _legacy_id), unidade in self.unidade_map.items() if unidade and table == "diocesanos"
            ]

            # Importar valor_regional e valor_diocesano como preço nas unidades
            # desses tipos, para materiais que não têm entrada em materiais_equipes
            cur.execute(
                "SELECT id, valor_regional, valor_diocesano "
                "FROM materiais WHERE deleted_at IS NULL"
            )
            material_rows = cur.fetchall()
            self.stdout.write(f"    {len(material_rows)} materiais para fallback de preço")
            for index, row in enumerate(material_rows, start=1):
                material = self.material_map.get(row["id"])
                if not material or self.dry_run:
                    continue

                valor_reg = row.get("valor_regional") or Decimal("0.00")
                valor_dio = row.get("valor_diocesano") or Decimal("0.00")

                # Aplicar valor_regional em todas as unidades do tipo REGIONAL
                if valor_reg:
                    for unidade_id in regionais_ids:
                        key = (unidade_id, material.id)
                        if key not in preco_map:
                            current = final_records.get(key, {"valor": Decimal("0.00"), "quantidade": 0})
                            final_records[key] = {
                                "valor": valor_reg,
                                "quantidade": current["quantidade"],
                            }

                # Aplicar valor_diocesano em todas as unidades do tipo DIOCESANO
                if valor_dio:
                    for unidade_id in diocesanos_ids:
                        key = (unidade_id, material.id)
                        if key not in preco_map:
                            current = final_records.get(key, {"valor": Decimal("0.00"), "quantidade": 0})
                            final_records[key] = {
                                "valor": valor_dio,
                                "quantidade": current["quantidade"],
                            }
                self._progress("Fallback de preços", index, len(material_rows))

            count = len(final_records)

            if not self.dry_run and final_records:
                self.stdout.write(f"    Gravando {count} registros em lote…")
                unidade_material_rows = [
                    UnidadeMaterial(
                        unidade_id=uid,
                        material_id=mid,
                        valor=data["valor"],
                        quantidade=data["quantidade"],
                    )
                    for (uid, mid), data in final_records.items()
                ]
                with transaction.atomic():
                    UnidadeMaterial.objects.bulk_create(
                        unidade_material_rows,
                        batch_size=1000,
                        update_conflicts=True,
                        update_fields=["valor", "quantidade", "updated_at"],
                        unique_fields=["unidade", "material"],
                    )
                self.stdout.write("    Gravação em lote concluída")

        if normalized_negative_stock:
            self.stdout.write(
                self.style.WARNING(
                    "    ⚠ "
                    f"{normalized_negative_stock} registros de estoque negativos no legado "
                    "foram importados com quantidade 0"
                )
            )
        self.stdout.write(f"  {count} registros de preço/estoque importados")

    # ─────────────────────────────────────────────────────────────────────
    # 5. Dados Bancários
    # ─────────────────────────────────────────────────────────────────────
    def _import_bancos(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando dados bancários…"))

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, fk_nivel, nivel, banco, agencia, conta, operacao, cnpj "
                "FROM dados_bancario WHERE deleted_at IS NULL ORDER BY id"
            )
            rows = cur.fetchall()

        if self.dry_run:
            self.stdout.write(f"  {len(rows)} dados bancários (dry-run)")
            return

        count = 0
        for i, row in enumerate(rows, 1):
            table = NIVEL_TO_TABLE.get(row.get("nivel"))
            if not table:
                self._progress("Dados bancários", i, len(rows))
                continue
            unidade = self.unidade_map.get((table, row["fk_nivel"]))
            if not unidade:
                self._progress("Dados bancários", i, len(rows))
                continue

            with transaction.atomic():
                DadoBancario.objects.update_or_create(
                    unidade=unidade,
                    defaults={
                        "banco": (row["banco"] or "")[:255],
                        "agencia": (row["agencia"] or "")[:255],
                        "conta": (row["conta"] or "")[:255],
                        "cnpj": (row.get("cnpj") or "")[:18],
                    },
                )
            count += 1
            self._progress("Dados bancários", i, len(rows))

        self.stdout.write(f"  {count} dados bancários importados")

    # ─────────────────────────────────────────────────────────────────────
    # 6. Equipes
    # ─────────────────────────────────────────────────────────────────────
    def _import_equipes(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando equipes…"))

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome FROM equipes WHERE deleted_at IS NULL ORDER BY id"
            )
            rows = cur.fetchall()

        if self.dry_run:
            for row in rows:
                self.equipe_map[row["id"]] = None
            self.stdout.write(f"  {len(rows)} equipes (dry-run)")
            return

        existing = {e.nome: e for e in Equipe.objects.all()}
        to_create = []

        for i, row in enumerate(rows, 1):
            nome = row["nome"] or f"Equipe {row['id']}"
            if nome in existing:
                self.equipe_map[row["id"]] = existing[nome]
            else:
                obj = Equipe(nome=nome)
                to_create.append((row["id"], obj))
            self._progress("Equipes", i, len(rows))

        if to_create:
            objs = [o for _, o in to_create]
            with transaction.atomic():
                Equipe.objects.bulk_create(objs, batch_size=BATCH_SIZE)
            all_equipes = {e.nome: e for e in Equipe.objects.all()}
            for legacy_id, obj in to_create:
                self.equipe_map[legacy_id] = all_equipes[obj.nome]

        all_equipes = {e.nome: e for e in Equipe.objects.all()}
        for row in rows:
            nome = row["nome"] or f"Equipe {row['id']}"
            if row["id"] not in self.equipe_map:
                self.equipe_map[row["id"]] = all_equipes.get(nome)

        self.stdout.write(f"  {len(rows)} equipes importadas")

    # ─────────────────────────────────────────────────────────────────────
    # 7. Casais (+ criação de Paróquia/Cidade quando necessário)
    # ─────────────────────────────────────────────────────────────────────
    def _import_casais(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando casais…"))

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, ele, ela, email_ele, email_ela, telefones, "
                "endereco, cidade, uf, dirigentes_id "
                "FROM casais WHERE deleted_at IS NULL ORDER BY id"
            )
            rows = cur.fetchall()

        self.stdout.write(f"    {len(rows)} registros lidos do MySQL")

        if self.dry_run:
            for row in rows:
                self.casal_map[row["id"]] = None
            self.stdout.write(f"  {len(rows)} casais (dry-run)")
            return

        count = 0
        for i, row in enumerate(rows, 1):
            paroquia = None
            dirigentes_id = row.get("dirigentes_id")
            if dirigentes_id:
                unidade_paroquia = self.unidade_map.get(("dirigentes", dirigentes_id))
                if unidade_paroquia:
                    cidade_nome = row.get("cidade") or ""
                    uf = row.get("uf") or ""
                    if cidade_nome and uf:
                        cidade = self._get_or_create_cidade(cidade_nome, uf)
                        paroquia = self._get_or_create_paroquia(
                            nome=unidade_paroquia.nome,
                            cidade=cidade,
                            unidade=unidade_paroquia,
                        )

            telefones_raw = row.get("telefones") or ""
            telefones = [t.strip() for t in telefones_raw.replace(";", "/").split("/") if t.strip()]
            tel_ele = telefones[0][:30] if len(telefones) >= 1 else None
            tel_ela = telefones[1][:30] if len(telefones) >= 2 else None

            with transaction.atomic():
                obj, _ = Casal.objects.update_or_create(
                    ele=row["ele"] or "",
                    ela=row["ela"] or "",
                    paroquia=paroquia,
                    defaults={
                        "email_ele": row.get("email_ele") or None,
                        "email_ela": row.get("email_ela") or None,
                        "telefone_ele": tel_ele,
                        "telefone_ela": tel_ela,
                    },
                )
            self.casal_map[row["id"]] = obj
            count += 1
            self._progress("Casais", i, len(rows))

        self.stdout.write(f"  {count} casais importados")

    # ─────────────────────────────────────────────────────────────────────
    # 8. Encontros
    # ─────────────────────────────────────────────────────────────────────
    def _import_encontros(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando encontros…"))

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, local, endereco, cidade, uf, data, etapa, casais, "
                "nivel, fk_nivel "
                "FROM encontros WHERE deleted_at IS NULL ORDER BY id"
            )
            rows = cur.fetchall()

        self.stdout.write(f"    {len(rows)} registros lidos do MySQL")

        if self.dry_run:
            for row in rows:
                self.encontro_map[row["id"]] = None
            self.stdout.write(f"  {len(rows)} encontros (dry-run)")
            return

        count = 0
        skipped = 0
        for i, row in enumerate(rows, 1):
            table = NIVEL_TO_TABLE.get(row.get("nivel"))
            if not table:
                skipped += 1
                self._progress("Encontros", i, len(rows))
                continue

            unidade = self.unidade_map.get((table, row["fk_nivel"]))
            if not unidade:
                skipped += 1
                self._progress("Encontros", i, len(rows))
                continue

            data = row.get("data")
            if not data:
                skipped += 1
                self._progress("Encontros", i, len(rows))
                continue

            etapa = row.get("etapa")
            try:
                etapa = int(etapa) if etapa else 0
            except (ValueError, TypeError):
                etapa = 0

            nome = row.get("local") or "S/N"

            paroquia = None
            if row.get("nivel") == 8 and row.get("fk_nivel"):
                unidade_dir = self.unidade_map.get(("dirigentes", row["fk_nivel"]))
                cidade_nome = row.get("cidade") or ""
                uf = row.get("uf") or ""
                if unidade_dir and cidade_nome and uf:
                    cidade = self._get_or_create_cidade(cidade_nome, uf)
                    paroquia = self._get_or_create_paroquia(
                        nome=unidade_dir.nome, cidade=cidade, unidade=unidade_dir
                    )

            with transaction.atomic():
                obj, _ = Encontro.objects.update_or_create(
                    nome=nome,
                    etapa=etapa,
                    data=data,
                    unidade=unidade,
                    defaults={"paroquia": paroquia},
                )
            self.encontro_map[row["id"]] = obj
            count += 1
            self._progress("Encontros", i, len(rows))

        self.stdout.write(f"  {count} encontros importados ({skipped} pulados)")

    # ─────────────────────────────────────────────────────────────────────
    # 9. CasalEncontro (casais_equipes)
    # ─────────────────────────────────────────────────────────────────────
    def _import_casal_encontro(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando casal × encontro…"))

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, casais_id, equipes_id, encontros_id "
                "FROM casais_equipes WHERE deleted_at IS NULL ORDER BY id"
            )
            rows = cur.fetchall()

        self.stdout.write(f"    {len(rows)} registros lidos do MySQL")

        if self.dry_run:
            self.stdout.write(f"  {len(rows)} vínculos (dry-run)")
            return

        count = 0
        for i, row in enumerate(rows, 1):
            casal = self.casal_map.get(row["casais_id"])
            encontro = self.encontro_map.get(row.get("encontros_id"))
            equipe = self.equipe_map.get(row.get("equipes_id"))

            if not casal or not encontro:
                self._progress("Casal-encontro", i, len(rows))
                continue

            with transaction.atomic():
                CasalEncontro.objects.update_or_create(
                    casal=casal,
                    encontro=encontro,
                    defaults={"equipe": equipe},
                )
            count += 1
            self._progress("Casal-encontro", i, len(rows))

        self.stdout.write(f"  {count} vínculos casal-encontro importados")

    # ─────────────────────────────────────────────────────────────────────
    # 10. Pedidos + PedidoMaterial
    # ─────────────────────────────────────────────────────────────────────
    def _import_pedidos(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando pedidos…"))

        STATUS_MAP = {
            1: Pedido.Status.NOVO,
            2: Pedido.Status.RECEBIDO,
            3: Pedido.Status.REALIZADO,
            4: Pedido.Status.CANCELADO,
        }

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, fk_nivel, nivel, status, endereco, cep, uf, cidade, "
                "telefone, correios, obs, solicitante "
                "FROM pedidos WHERE deleted_at IS NULL ORDER BY id"
            )
            pedidos_rows = cur.fetchall()
            self.stdout.write(f"    {len(pedidos_rows)} pedidos lidos do MySQL")

            count = 0
            skipped = 0
            for i, row in enumerate(pedidos_rows, 1):
                if self.dry_run:
                    self.pedido_map[row["id"]] = None
                    count += 1
                    self._progress("Pedidos", i, len(pedidos_rows))
                    continue

                table = NIVEL_TO_TABLE.get(row.get("nivel"))
                if not table:
                    skipped += 1
                    self._progress("Pedidos", i, len(pedidos_rows))
                    continue

                unidade = self.unidade_map.get((table, row["fk_nivel"]))
                if not unidade:
                    skipped += 1
                    self._progress("Pedidos", i, len(pedidos_rows))
                    continue

                cidade_nome = row.get("cidade") or ""
                uf = row.get("uf") or ""
                cidade = self._get_or_create_cidade(cidade_nome, uf) if cidade_nome and uf else None
                if not cidade:
                    cidade = self._get_or_create_cidade("Não informada", "XX")

                status_legado = row.get("status") or 1
                status_django = STATUS_MAP.get(status_legado, Pedido.Status.NOVO)
                solicitante = row.get("solicitante") or unidade.nome

                with transaction.atomic():
                    pedido = Pedido.objects.create(
                        solicitante=solicitante,
                        unidade=unidade,
                        cidade=cidade,
                        status=status_django,
                        endereco=row.get("endereco") or "",
                        cep=row.get("cep") or "",
                        telefones=row.get("telefone") or "",
                        codigo_correios=row.get("correios") or "",
                        obs=row.get("obs") or "",
                    )
                self.pedido_map[row["id"]] = pedido
                count += 1
                self._progress("Pedidos", i, len(pedidos_rows))

            # Itens do pedido
            cur.execute(
                "SELECT pm.id, pm.pedidos_id, pm.materiais_id, pm.quantidade, "
                "pm.valor_unitario, pm.total "
                "FROM pedidos_materiais pm "
                "INNER JOIN pedidos p ON p.id = pm.pedidos_id AND p.deleted_at IS NULL "
                "WHERE pm.deleted_at IS NULL "
                "ORDER BY pm.id"
            )
            itens_rows = cur.fetchall()
            self.stdout.write(f"    {len(itens_rows)} itens de pedido lidos do MySQL")

            count_itens = 0
            for i, row in enumerate(itens_rows, 1):
                if self.dry_run:
                    count_itens += 1
                    self._progress("Itens de pedido", i, len(itens_rows))
                    continue

                pedido = self.pedido_map.get(row["pedidos_id"])
                material = self.material_map.get(row["materiais_id"])
                if not pedido or not material:
                    self._progress("Itens de pedido", i, len(itens_rows))
                    continue

                valor = row.get("valor_unitario") or Decimal("0.00")

                with transaction.atomic():
                    PedidoMaterial.objects.update_or_create(
                        pedido=pedido,
                        material=material,
                        defaults={
                            "quantidade": row["quantidade"] or 0,
                            "valor_venda": valor,
                        },
                    )
                count_itens += 1
                self._progress("Itens de pedido", i, len(itens_rows))

        self.stdout.write(f"  {count} pedidos e {count_itens} itens importados ({skipped} pulados)")

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────
    def _get_or_create_cidade(self, nome: str, uf: str) -> Cidade:
        nome = nome.strip().title()
        uf = uf.strip().upper()[:2]
        key = (nome, uf)
        if key in self.cidade_cache:
            return self.cidade_cache[key]
        obj, _ = Cidade.objects.get_or_create(nome=nome, uf=uf)
        self.cidade_cache[key] = obj
        return obj

    def _get_or_create_paroquia(self, *, nome: str, cidade: Cidade, unidade: Unidade) -> Paroquia:
        key = (nome, cidade.id, unidade.id)
        if key in self.paroquia_cache:
            return self.paroquia_cache[key]
        obj, _ = Paroquia.objects.get_or_create(
            nome=nome, cidade=cidade, unidade=unidade,
        )
        self.paroquia_cache[key] = obj
        return obj
