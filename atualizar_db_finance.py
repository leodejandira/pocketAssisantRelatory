from supabase import create_client, Client
from datetime import datetime
import decimal

# Defina as credenciais do Supabase
SUPABASE_URL = "https://pnwkvrfshrthgtujmnkv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBud2t2cmZzaHJ0aGd0dWptbmt2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA1NDgyNDksImV4cCI6MjA3NjEyNDI0OX0.NyYFRbz81kJsXLXJJc9X92NVM_Zg-K29A2JuufnbWxA"

# Crie a instância do cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_pagamentos_divida():
    today = datetime.today()
    start_of_month = today.replace(day=1)
    end_of_month = today.replace(month=today.month + 1, day=1) if today.month != 12 else today.replace(year=today.year + 1, month=1, day=1)

    tipo_id = 7

    response = supabase.table("financ_regis").select("valor").eq("tipo_id", tipo_id)\
        .gte("data_registro", start_of_month).lt("data_registro", end_of_month).execute()

    total_divida = sum([record["valor"] for record in response.data])
    
    return decimal.Decimal(-abs(total_divida))

def get_compras_a_prazo():
    today = datetime.today()
    start_of_month = today.replace(day=1)
    end_of_month = today.replace(month=today.month + 1, day=1) if today.month != 12 else today.replace(year=today.year + 1, month=1, day=1)

    response = supabase.table("compras_a_prazo").select("valor")\
        .gte("data_registro", start_of_month).lt("data_registro", end_of_month).execute()

    total_compras = sum([record["valor"] for record in response.data])
    return decimal.Decimal(total_compras)

def get_reservas_mes_vigente():
    today = datetime.today()
    start_of_month = today.replace(day=1)
    end_of_month = today.replace(month=today.month + 1, day=1) if today.month != 12 else today.replace(year=today.year + 1, month=1, day=1)

    # Buscar lançamentos que contenham "Reserva" no nome
    response = supabase.table("financ_regis").select("valor, nome")\
        .ilike("nome", "%Reserva%")\
        .gte("data_registro", start_of_month).lt("data_registro", end_of_month).execute()

    total_reserva = decimal.Decimal(0)
    reservas_encontradas = []

    for record in response.data:
        # CORREÇÃO: Converter valores negativos para positivos
        valor_positivo = abs(decimal.Decimal(record["valor"]))
        total_reserva += valor_positivo
        reservas_encontradas.append({
            "nome": record["nome"],
            "valor_original": record["valor"],
            "valor_positivo": float(valor_positivo)
        })

    print(f"Encontradas {len(reservas_encontradas)} reservas no mês:")
    for reserva in reservas_encontradas:
        print(f"  - {reserva['nome']}: R${reserva['valor_original']:.2f} → R${reserva['valor_positivo']:.2f}")

    return total_reserva

def atualizar_reserva(total_reserva):
    # Converter o valor Decimal para float
    total_reserva_float = float(total_reserva)
    
    # Converter a data para string no formato 'YYYY-MM-DD'
    data_registro_str = datetime.today().date().strftime('%Y-%m-%d')

    # Verificar se já existe registro de reserva para hoje
    response = supabase.table("reserva").select("id").eq("data_registro", data_registro_str).execute()
    
    if response.data:
        # Atualizar registro existente
        supabase.table("reserva").update({
            "valor": total_reserva_float
        }).eq("data_registro", data_registro_str).execute()
        print(f"Reserva atualizada: R${total_reserva_float:.2f}")
    else:
        # Inserir novo registro
        supabase.table("reserva").insert({
            "valor": total_reserva_float,
            "data_registro": data_registro_str
        }).execute()
        print(f"Reserva inserida: R${total_reserva_float:.2f}")

def atualizar_divida():
    # Primeiro, apagar o registro errado se existir
    try:
        data_hoje = datetime.today().date().strftime('%Y-%m-%d')
        supabase.table("cc_e_dividas").delete().eq("data_registro", data_hoje).execute()
        print("Registro errado de hoje foi apagado")
    except Exception as e:
        print(f"Erro ao apagar registro: {e}")

    # Obter os valores
    total_divida = get_pagamentos_divida()
    total_compras_a_prazo = get_compras_a_prazo()

    print(f"Total pagamentos dívida: R${total_divida:.2f}")
    print(f"Total compras a prazo: R${total_compras_a_prazo:.2f}")

    # Pegar o valor da divida do mês passado (último registro na tabela CC_e_dividas)
    response = supabase.table("cc_e_dividas").select("valor").order("data_registro", desc=True).limit(1).execute()
    valor_mes_passado = decimal.Decimal(response.data[0]["valor"]) if response.data else decimal.Decimal(0)

    print(f"Valor mês passado: R${valor_mes_passado:.2f}")

    # Calcular o novo valor CORRETAMENTE
    novo_valor = valor_mes_passado + total_compras_a_prazo + total_divida

    # Converter o valor Decimal para float
    novo_valor_float = float(novo_valor)

    # Inserir o novo valor na tabela CC_e_dividas
    supabase.table("cc_e_dividas").insert({
        "valor": novo_valor_float,
        "data_registro": data_hoje
    }).execute()

    print(f"Novo valor atualizado na tabela CC_e_dividas: R${novo_valor_float:.2f}")
    print(f"Detalhamento: R${valor_mes_passado:.2f} (mês passado) + R${total_compras_a_prazo:.2f} (compras) + R${total_divida:.2f} (pagamentos) = R${novo_valor_float:.2f}")

def main():
    print("=== ATUALIZANDO DÍVIDAS ===")
    atualizar_divida()
    
    print("\n=== ATUALIZANDO RESERVAS ===")
    total_reserva = get_reservas_mes_vigente()
    print(f"Total de reservas do mês: R${total_reserva:.2f}")
    
    atualizar_reserva(total_reserva)
    
    print("\n=== PROCESSO CONCLUÍDO ===")

# Rodar o script
if __name__ == "__main__":
    main()