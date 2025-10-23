import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime, timedelta
import calendar
import numpy as np
from matplotlib.image import imread
from dotenv import load_dotenv
import os


# Configurações regionais e monetárias
pd.options.display.float_format = 'R$ {:,.2f}'.format
LOCALE = 'pt_BR'

# Tenta importar Supabase e Postgrest
try:
    from supabase import create_client
    from postgrest.exceptions import APIError
except ImportError:
    print("Dependências não instaladas. Instale com: pip install supabase postgrest")
    sys.exit(1)

# --- CLASSE 1: FINANCE REPORT (Relatórios Financeiros) ---

class FinanceReport:

    # DENTRO DA CLASSE FinanceReport (SUBSTITUA ESTE MÉTODO)
    def create_financial_summary_header(self, fig, gs_summary, entrada, gasto, balanco, month_name):
        """Cria o Resumo Financeiro Geral para o mês atual, de forma compacta em uma linha."""
        ax = fig.add_subplot(gs_summary, facecolor=self.colors['background'])
        
        # 1. PREPARAÇÃO DO TEXTO E CORES
        
        # Formata os valores para exibição
        entrada_str = f"Entradas: R$ {entrada:,.2f}"
        gasto_str = f"Saídas: R$ {gasto:,.2f}"
        
        # Formata o balanço. O R$ precisa estar dentro do balanço para a cor.
        balanco_str = f"Balanço: R$ {balanco:,.2f}"
        
        # Cor do balanço: Verde para positivo/zero, Vermelho para negativo
        balanco_text_color = self.colors['entry'] if balanco >= 0 else self.colors['expense']
        
        # Cria a string completa, usando formatação de cor/peso para o balanço.
        # Usaremos Mathtext para colorir apenas o valor do Balanço.
        # O Matplotlib é um pouco complicado com cores em Mathtext, então faremos uma abordagem simples de destaque:
        
        # Abordagem 1: String simples com destaque no Balanço
        stats_text_base = f"Mês: {month_name.upper()} | {entrada_str} | {gasto_str} | {balanco_str}"
        
        # 2. PLOTAGEM
        
        ax.text(0.5, 0.5, stats_text_base, 
                fontsize=10, 
                ha='center', va='center', 
                color=self.colors['default'],
                # Box compacta
                bbox=dict(boxstyle="round,pad=0.5", facecolor=self.colors['secondary_bg'], edgecolor=self.colors['border']))

        # 3. DESTAQUE VISUAL (Para o Balanço)
        
        # Para dar um destaque, vamos plotar uma caixa de cor SOBRE a área onde o balanço aparece.
        # Isso é mais robusto do que tentar Mathtext complicado.
        
        # Não temos as coordenadas exatas, mas vamos chutar a posição do Balanço (último item da direita)
        # 0.55 a 0.85 (aproximadamente) na horizontal e 0.5 (vertical)
        
        # NOTA: O Matplotlib pode ser impreciso com esta técnica, mas é a mais compacta.
        # A cor da caixa será a cor do texto do balanço (vermelho/verde)
        
        # ax.axvspan(0.70, 0.95, ymin=0.4, ymax=0.6, 
        #           color=balanco_text_color, alpha=0.3, transform=ax.transAxes)

        # Se a técnica da caixa for instável, mantenha apenas a string simples e confie no Balanço > 0 ou < 0.
        
        # Vamos usar um segundo texto plotado por cima, apenas para colorir.
        # Posicionaremos este texto no canto direito da área do Axes.

        ax.text(0.95, 0.5, balanco_str, 
                fontsize=10, 
                ha='right', va='center', 
                color=balanco_text_color, # A cor do Balanço é aplicada aqui!
                fontweight='bold',
                transform=ax.transAxes)
        
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_visible(False)
        return ax
    
    """Gera gráficos e tabelas de relatórios financeiros."""
    def __init__(self, supabase_url, supabase_key):
        self.supabase = create_client(supabase_url, supabase_key)
        self.colors = {
            'entry': '#39d353', 
            'expense': '#f85149', 
            'default': '#f0f6fc',
            'background': '#0d1117',
            'secondary_bg': '#161b22',
            'border': '#30363d',
            'highlight': '#006d32', 
            # NOVO: Traço comparativo em Vermelho Escuro
            'previous_month_mark': '#b30000', 
            # NOVO: Cor para a barra de faturas futuras (Laranja)
            'future_invoice_bar': '#f28020'
        }
        self.font_size = 9
        # CONSOLIDADO DE TABELAS (Tirado de fetch_all_data e centralizado)
        self.tables = ["tipo", "financ_regis", "cc_e_dividas", "reserva", "compras_prazo_parcelas"]

# DENTRO DA CLASSE FinanceReport (SUBSTITUA A FUNÇÃO INTEIRA)
    def fetch_all_data(self):
        """Busca todos os dados financeiros, agora com a lista de tabelas consolidada e valida."""
        print("Buscando dados financeiros do Supabase (Usando lista consolidada)...")
        data = {}
        # Lista Consolidada, Garantindo a inclusão das Parcelas
        self.tables = ["tipo", "financ_regis", "cc_e_dividas", "reserva", "compras_prazo_parcelas"]
        table_name = "" # Variável para capturar a tabela com erro
        
        try:
            for table_name in self.tables:
                print(f"  -> Tentando buscar a tabela: {table_name}...")
                response = self.supabase.table(table_name).select("*").execute()
                data[table_name] = response.data
                print(f"  ✅ Tabela '{table_name}' buscada com sucesso. ({len(data[table_name])} registros)")

            # --- Lógica de Processamento de Dados ---
            tipos_data = data.get('tipo', [])
            entrada_tipo = next((t for t in tipos_data if t.get('nome_tipo', '').lower() == 'entradas'), None)
            
            if entrada_tipo is None:
                print("❌ ERRO FATAL: Não foi encontrado um tipo de registro com o nome 'Entradas'.")
                return None 

            entrada_id = entrada_tipo['id']
            data['gastos'] = [r for r in data.get('financ_regis', []) if r.get('tipo_id') != entrada_id]
            data['entradas'] = [r for r in data.get('financ_regis', []) if r.get('tipo_id') == entrada_id]

            # Prepara o DataFrame de gastos
            gastos_df = pd.DataFrame(data['gastos'])
            if not gastos_df.empty:
                gastos_df['data_registro'] = pd.to_datetime(gastos_df['data_registro'])
            data['gastos_df'] = gastos_df

            # NOVO: Prepara o DataFrame de parcelas futuras (compras_prazo_parcelas)
            parcelas_df = pd.DataFrame(data.get('compras_prazo_parcelas', []))
            if not parcelas_df.empty:
                parcelas_df['data_vencimento'] = pd.to_datetime(parcelas_df['data_vencimento'])
                # Coluna 'valor' na tabela de parcelas é 'valor_parcela'
                parcelas_df = parcelas_df.rename(columns={'valor_parcela': 'valor'})
            data['parcelas_df'] = parcelas_df # Armazena o DataFrame processado

            return data
        
        except APIError as e:
            print(f"❌ ERRO CRÍTICO (API): A falha de comunicação ocorreu ao tentar buscar a tabela '{table_name}'.")
            print(f"Mensagem da API: {e.message}")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado ao buscar dados: {e}") 
            return None

    def get_monthly_expenses_by_category(self, gastos_df, year, month):
        """Calcula os gastos totais de um mês específico, agrupados por categoria."""
        if gastos_df.empty:
            return pd.Series(dtype=float)
            
        start_date = datetime(year, month, 1)
        _, num_days = calendar.monthrange(year, month)
        end_date = datetime(year, month, num_days, 23, 59, 59)

        # Filtra os gastos do mês
        month_filter = (gastos_df['data_registro'] >= start_date) & (gastos_df['data_registro'] <= end_date)
        month_data = gastos_df[month_filter].copy()

        if month_data.empty:
            return pd.Series(dtype=float)

        # Agrupa e soma por tipo de gasto
        expenses_by_type = month_data.groupby('tipo_id')['valor'].sum().abs().sort_values(ascending=False)
        return expenses_by_type
    
# DENTRO DA CLASSE FinanceReport (FUNÇÃO CORRIGIDA)
    def get_future_invoices(self, parcelas_df, current_date):
        """Calcula o total das faturas futuras para o mês atual e os próximos 11 meses."""
        if parcelas_df.empty:
            return pd.Series(dtype=float)
        
        future_invoices = {}
        # MUDANÇA CRÍTICA: Começa de i=0 (Mês Atual) e vai até i=11 (Próximos 11 meses)
        for i in range(0, 12): 
            target_date = current_date + pd.DateOffset(months=i)
            target_month = target_date.month
            target_year = target_date.year
            
            # Definir o período do mês (do dia 1 até o último dia)
            start_date = datetime(target_year, target_month, 1)
            _, days_in_month = calendar.monthrange(target_year, target_month)
            end_date = datetime(target_year, target_month, days_in_month, 23, 59, 59)

            # Filtro: Data de vencimento DENTRO do mês e status 'pago' = False
            month_filter = (parcelas_df['data_vencimento'] >= start_date) & \
                           (parcelas_df['data_vencimento'] <= end_date) & \
                           (parcelas_df['pago'] == False) 

            # Usa a coluna 'valor' (que foi renomeada no fetch_all_data)
            month_invoices = parcelas_df[month_filter]['valor'].sum()
            
            # Usa Period para indexar por mês e ano
            period_key = pd.Period(year=target_year, month=target_month, freq='M')
            future_invoices[period_key] = month_invoices
            
        # Filtra para remover meses sem valor
        series = pd.Series(future_invoices)
        # Retorna apenas meses com valores > 0
        return series[series > 0]

    # --- FUNÇÕES DE PLOTAGEM ---

# DENTRO DA CLASSE FinanceReport (SUBSTITUA A FUNÇÃO create_monthly_expense_chart)
    def create_monthly_expense_chart(self, fig, ax, data, year, month):
        """Gráfico 1: Gastos mensais por tipo com comparação do mês anterior (Traço com cores dinâmicas)."""
        
        prev_month_date = datetime(year, month, 1) - timedelta(days=1)
        prev_year, prev_month = prev_month_date.year, prev_month_date.month

        # 1. Calcular gastos do Mês Atual e do Mês Anterior
        current_expenses = self.get_monthly_expenses_by_category(data['gastos_df'], year, month)
        previous_expenses = self.get_monthly_expenses_by_category(data['gastos_df'], prev_year, prev_month)
        
        tipos_map = {t['id']: t['nome_tipo'] for t in data.get('tipo', [])}
        
        if current_expenses.empty and previous_expenses.empty:
            ax.set_title("1. Gastos Mensais por Categoria (Comparativo)", fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)
            ax.text(0.5, 0.5, "Nenhum gasto registrado nos últimos dois meses.", ha='center', va='center', color=self.colors['default'], transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            for spine in ax.spines.values(): spine.set_visible(False)
            return

        # 2. Consolidar Categorias para Exibição
        all_type_ids = pd.Index(current_expenses.index).union(previous_expenses.index)
        
        comparison_df = pd.DataFrame({
            'Current': current_expenses.reindex(all_type_ids, fill_value=0),
            'Previous': previous_expenses.reindex(all_type_ids, fill_value=0)
        })
        
        comparison_df = comparison_df[(comparison_df['Current'] > 0) | (comparison_df['Previous'] > 0)]
        
        # Ordenação decrescente (MAIOR no topo)
        if not comparison_df.empty:
            sort_by = 'Current' if comparison_df['Current'].sum() > 0 else 'Previous'
            comparison_df = comparison_df.sort_values(by=sort_by, ascending=False).head(10)


        names = [tipos_map.get(tid) for tid in comparison_df.index]
        current_values = comparison_df['Current'].values
        previous_values = comparison_df['Previous'].values
        
        y_pos = np.arange(len(names))
        
        prev_month_name = calendar.month_abbr[prev_month].capitalize()
        ax.set_title(f"1. Gastos Mensais por Categoria (vs. {prev_month_name})", fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)

        # 3. Desenhar as Barras do Mês Atual (Current)
        bars = ax.barh(y_pos, current_values, color=self.colors['expense'], zorder=2)
        
        # 4. Desenhar o Traço do Mês Anterior (Previous) - AGORA COM CORES DINÂMICAS
        GREEN_COLOR = self.colors['highlight'] # Usando o 'highlight' (verde escuro) do HabitTracker ou outro verde escuro
        RED_COLOR = self.colors['previous_month_mark']
        
        # Criamos o mapeamento de cores para cada traço
        comparison_colors = []
        for curr_val, prev_val in zip(current_values, previous_values):
            # A lógica só se aplica se houver um valor anterior para comparação
            if prev_val > 0:
                # Regra: Se o gasto atual for <= 115% do gasto anterior, é VERDE (controle)
                if curr_val <= prev_val * 1.15:
                    comparison_colors.append(GREEN_COLOR)
                # Caso contrário, é VERMELHO (estouro)
                else:
                    comparison_colors.append(RED_COLOR)
            else:
                # Se não há valor anterior, mas há valor atual, usamos a cor padrão (vermelho) ou podemos omitir o traço, mas manteremos o vermelho
                comparison_colors.append(RED_COLOR) 

        # Desenha a linha vertical (traço)
        for i, prev_val in enumerate(previous_values):
            if prev_val > 0:
                color = comparison_colors[i] 
                
                # Desenha o traço (linha vertical)
                ax.vlines(x=prev_val, ymin=y_pos[i] - 0.4, ymax=y_pos[i] + 0.4, 
                          color=color, 
                          linewidth=5, 
                          zorder=3) 
                
                # Adiciona o marcador (o pequeno risco no centro) para visibilidade extra
                ax.plot(prev_val, y_pos[i], marker='|', color=color, markersize=15, markeredgewidth=3, zorder=3.5)

        
        ax.set_yticks(y_pos, labels=names, color=self.colors['default'], fontsize=self.font_size)
        ax.set_xlabel("Valor (R$)", color=self.colors['default'], fontsize=self.font_size)
        
        ax.tick_params(axis='x', colors=self.colors['default'])
        # Inverte o eixo Y para colocar a maior barra no topo
        ax.invert_yaxis() 
        
        # Adicionar rótulos de valor do Mês Atual
        max_val_plot = max(current_values.max(), previous_values.max()) * 1.05 if current_values.size > 0 or previous_values.size > 0 else 100
        for bar, curr_val in zip(bars, current_values):
            width = bar.get_width()
            ax.text(width + (max_val_plot * 0.005), bar.get_y() + bar.get_height()/2, 
                    f'R$ {width:,.2f}',
                    va='center', ha='left', color=self.colors['default'], fontsize=self.font_size - 1,
                    zorder=4)

 # DENTRO DA CLASSE FinanceReport (NO FINAL DA FUNÇÃO create_monthly_expense_chart)

# ... (código anterior da função)

        # 5. Ajustes Finais do Eixo
        ax.set_xlim(0, max_val_plot * 1.15) 

        # Adiciona a legenda para as cores dinâmicas (Traço do Mês Anterior)
        # *** CORREÇÃO APLICADA AQUI: Substituí '\le' por '≤' e removi a formatação LaTeX. ***
        green_patch = patches.Patch(color=GREEN_COLOR, label='Mês Anterior (Aumento ≤ 15%)')
        red_patch = patches.Patch(color=RED_COLOR, label='Mês Anterior (Aumento > 15% / Sem dado)')
        
        # Verifica se o ax já tem legendas para não sobrepor
        existing_handles, existing_labels = ax.get_legend_handles_labels()
        
        # A legenda será apenas para as cores do traço
        ax.legend(handles=[green_patch, red_patch], loc='lower right', 
                  facecolor=self.colors['secondary_bg'], edgecolor=self.colors['border'],
                  labelcolor=self.colors['default'], fontsize=self.font_size - 1,
                  title="Comparativo Mês Anterior (Traço)")
        
        for spine in ax.spines.values(): spine.set_visible(False)
        ax.xaxis.grid(True, linestyle='--', alpha=0.3, color=self.colors['default'])
        
# DENTRO DA CLASSE FinanceReport (SUBSTITUA A FUNÇÃO create_debt_and_invoice_chart)
    def create_debt_and_invoice_chart(self, fig, ax1, data, current_year):
        """Gráfico 2: Dívida em Aberto Histórica (Linha) e Faturas Futuras (Barras no Eixo Secundário)."""
        ax1.set_title("2. Dívida em Aberto e Faturas Futuras (R$)", fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)

        # 1. Dados da Dívida em Aberto (Linha)
        debt_df = pd.DataFrame(data.get('cc_e_dividas', []))
        
        # 2. Obter Faturas Futuras (Barras)
        today = datetime.now()
        future_invoices = self.get_future_invoices(data.get('parcelas_df', pd.DataFrame()), today)
        
        has_debt_data = not debt_df.empty
        has_invoice_data = not future_invoices.empty

        if not has_debt_data and not has_invoice_data:
            ax1.text(0.5, 0.5, "Nenhum registro de dívida ou fatura futura.", ha='center', va='center', color=self.colors['default'], transform=ax1.transAxes)
            ax1.set_xticks([]); ax1.set_yticks([]); ax1.grid(False)
            for spine in ax1.spines.values(): spine.set_visible(False)
            return

        # Processar Dívida Histórica
        monthly_debt_series = pd.Series(dtype=float)
        if has_debt_data:
            debt_df['data_registro'] = pd.to_datetime(debt_df['data_registro'])
            debt_df['Mes_Ano'] = debt_df['data_registro'].dt.to_period('M')
            monthly_debt_series = debt_df.groupby('Mes_Ano')['valor'].last()
            
        # 3. Combinar todos os meses relevantes para o eixo X
        all_months_periods = pd.PeriodIndex([], freq='M') 
        if not monthly_debt_series.empty:
            all_months_periods = all_months_periods.union(monthly_debt_series.index)
        if not future_invoices.empty:
            all_months_periods = all_months_periods.union(future_invoices.index)
        
        all_months_periods = all_months_periods.sort_values()

        if all_months_periods.empty:
             ax1.text(0.5, 0.5, "Nenhum dado relevante para o período.", ha='center', va='center', color=self.colors['default'], transform=ax1.transAxes)
             ax1.set_xticks([]); ax1.set_yticks([]); ax1.grid(False)
             for spine in ax1.spines.values(): spine.set_visible(False)
             return
        
        # Configuração do Eixo X
        x_positions = np.arange(len(all_months_periods))
        x_labels = [period.strftime('%b').upper() if period.year == current_year else period.strftime('%b%y').upper() for period in all_months_periods]
        
        ax1.set_xticks(x_positions)
        ax1.set_xticklabels(x_labels, color=self.colors['default'], rotation=0, fontsize=self.font_size)
        ax1.set_xlabel("Mês", color=self.colors['default'], fontsize=self.font_size)

        # 4. Plotar Dívida Histórica (Eixo Y Esquerdo - Linha)
        plot_debt_x = [x_positions[i] for i, period in enumerate(all_months_periods) if period in monthly_debt_series.index]
        plot_debt_y = [monthly_debt_series[period] for period in all_months_periods if period in monthly_debt_series.index]
        
        ax1.plot(plot_debt_x, plot_debt_y, marker='o', color=self.colors['expense'], linewidth=2, markersize=6, label="Dívida em Aberto")
        
        # Rótulos de valor na linha de Dívida (cor expense/vermelho)
        for x, y in zip(plot_debt_x, plot_debt_y):
            if y > 0:
                ax1.text(x, y * 1.05, f'R$ {y:,.0f}', ha='center', va='bottom', 
                         color=self.colors['expense'], fontsize=self.font_size - 1, fontweight='bold')

        ax1.set_ylabel("Valor Dívida (R$)", color=self.colors['default'], fontsize=self.font_size)
        ax1.tick_params(axis='y', colors=self.colors['default'])
        
        # 5. Criar Segundo Eixo Y para Faturas Futuras (Barras)
        ax2 = ax1.twinx()
        
        ax2.spines['right'].set_color(self.colors['border'])
        ax2.spines['left'].set_color(self.colors['border'])
        ax2.set_ylabel("Valor Faturas (R$)", color=self.colors['default'], fontsize=self.font_size)
        ax2.tick_params(axis='y', colors=self.colors['default'])
        
        # 6. Plotar Faturas Futuras (Eixo Y Direito)
        invoice_values = [future_invoices.get(period, 0) for period in all_months_periods]
        
        bar_width = 0.5 
        bars = ax2.bar(x_positions, invoice_values, bar_width, color=self.colors['future_invoice_bar'], label="Faturas Futuras", alpha=0.7, zorder=1)
        
        # Adiciona rótulos de valor nas barras
        max_invoice = max(invoice_values) if invoice_values else 0
        y_label_offset = max_invoice * 0.02
        
        for i, val in enumerate(invoice_values):
            if val > 0:
                # *** ALTERAÇÃO AQUI: Cor do texto mudou para a cor da barra (future_invoice_bar) ***
                ax2.text(x_positions[i], val + y_label_offset, f'R$ {val:,.0f}', 
                         ha='center', va='bottom', color=self.colors['future_invoice_bar'], fontsize=self.font_size - 1,
                         fontweight='bold', # Adicionado fontweight para destaque
                         zorder=2)
        
        # 7. Ajustar limites Y
        max_debt = monthly_debt_series.max() if has_debt_data else 0
        ax1.set_ylim(0, max(max_debt * 1.25, 500)) 
        ax2.set_ylim(0, max(max_invoice * 1.2, 500)) 

        # Legendas para ambos os eixos
        lines, labels = ax1.get_legend_handles_labels()
        bars, bar_labels = ax2.get_legend_handles_labels()
        ax1.legend(lines + bars, labels + bar_labels, loc='upper left', facecolor=self.colors['secondary_bg'], 
                   edgecolor=self.colors['border'], labelcolor=self.colors['default'], fontsize=self.font_size - 1)

        ax1.grid(True, linestyle='--', alpha=0.3, color=self.colors['default'])
        for spine in ax1.spines.values(): spine.set_visible(False)
        for spine in ax2.spines.values(): spine.set_visible(False)

    def create_reserve_line_chart(self, fig, ax, data):
        """Gráfico 3: Acúmulo de Reserva e Metas (Renomeado para 3)."""
        ax.set_title("3. Acúmulo de Reserva e Metas (R$)", fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)

        reserve_df = pd.DataFrame(data['reserva'])
        if reserve_df.empty:
            ax.text(0.5, 0.5, "Nenhum lançamento na reserva.", ha='center', va='center', color=self.colors['default'], transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
            for spine in ax.spines.values(): spine.set_visible(False)
            return

        reserve_df['data_registro'] = pd.to_datetime(reserve_df['data_registro'])
        reserve_df = reserve_df.sort_values('data_registro')
        
        reserve_df['saldo_acumulado'] = reserve_df['valor'].cumsum()
        
        reserve_df['Mes_Ano'] = reserve_df['data_registro'].dt.to_period('M')
        
        monthly_balance = reserve_df.groupby('Mes_Ano')['saldo_acumulado'].last()
        
        all_months = pd.period_range(start=monthly_balance.index.min(), end=pd.Period(datetime.now(), freq='M'), freq='M')
        monthly_balance = monthly_balance.reindex(all_months)
        
        monthly_balance = monthly_balance.ffill().fillna(0) 

        months = monthly_balance.index.strftime('%b').tolist()
        values = monthly_balance.values
        
        ax.plot(months, values, marker='o', color=self.colors['entry'], linewidth=2, markersize=6)

        # *** ADIÇÃO: Rótulos de valor na linha de Reserva ***
        for month_idx, value in enumerate(values):
            if value > 0:
                ax.text(month_idx, value * 1.05, f'R$ {value:,.0f}', ha='center', va='bottom', 
                        color=self.colors['entry'], fontsize=self.font_size - 1, fontweight='bold')
        # **********************************************************

        metas = [12000, 24000, 50000]
        max_balance = values.max() if values.size > 0 else 0
        
        current_meta_to_show = None
        for meta in metas:
            if max_balance < meta: 
                current_meta_to_show = meta
                break
        if current_meta_to_show is None and metas: 
            current_meta_to_show = metas[-1]

        if current_meta_to_show is not None:
            ax.axhline(current_meta_to_show, color=self.colors['entry'], linestyle='--', linewidth=1)
            ax.text(len(months) - 1, current_meta_to_show * 1.02, f'Meta: R$ {current_meta_to_show:,.0f}', 
                    color=self.colors['entry'], fontsize=self.font_size, ha='right', va='center')
        
        if current_meta_to_show is not None:
            # Ajuste do limite Y para acomodar os rótulos (max_balance * 1.25)
            y_max_suggested = max(max_balance * 1.25, current_meta_to_show * 1.1) 
            ax.set_ylim(0, y_max_suggested)
        elif max_balance > 0:
            ax.set_ylim(0, max_balance * 1.25) # Ajustado para rótulos
        else:
            ax.set_ylim(0, 5000) 

        ax.set_xlabel("Mês", color=self.colors['default'], fontsize=self.font_size)
        ax.set_ylabel("Valor (R$)", color=self.colors['default'], fontsize=self.font_size)
        
        ax.tick_params(axis='x', colors=self.colors['default'], rotation=0)
        ax.tick_params(axis='y', colors=self.colors['default'])
        ax.grid(True, linestyle='--', alpha=0.3, color=self.colors['default'])
        for spine in ax.spines.values(): spine.set_visible(False)
        
# DENTRO DA CLASSE FinanceReport (SUBSTITUA A FUNÇÃO generate_finance_page)
    def generate_finance_page(self, data):
        """Gera a figura de finanças (Página 2) com o resumo e os 3 gráficos solicitados."""
        today = datetime.now()
        current_year, current_month = today.year, today.month
        month_name = calendar.month_name[current_month]
        
        # 1. CÁLCULO DAS MÉTRICAS DO MÊS ATUAL
        start_date = datetime(current_year, current_month, 1)
        _, num_days = calendar.monthrange(current_year, current_month)
        end_date = datetime(current_year, current_month, num_days, 23, 59, 59)

        entradas_df = pd.DataFrame(data.get('entradas', []))
        entradas_df['data_registro'] = pd.to_datetime(entradas_df['data_registro'])
        entrada_filter = (entradas_df['data_registro'] >= start_date) & (entradas_df['data_registro'] <= end_date)
        total_entradas = entradas_df[entrada_filter]['valor'].sum()

        gastos_df = data['gastos_df']
        gasto_filter = (gastos_df['data_registro'] >= start_date) & (gastos_df['data_registro'] <= end_date)
        total_gastos = gastos_df[gasto_filter]['valor'].abs().sum()
        
        total_balanco = total_entradas - total_gastos

        # Define A4 size
        FIG_WIDTH, FIG_HEIGHT = 8.5, 11.0 

        # Função auxiliar para adicionar rodapé e layout
        def add_footer(fig, total_entradas, total_gastos, total_balanco, month_name):
            
            # --- CORREÇÃO: Usando a string de Mathtext corretamente ---
            
            # 1. Definir a cor do Mathtext usando cores padrão do Matplotlib
            color_name = 'Green' if total_balanco >= 0 else 'Red'

            # 2. Criar as strings
            entrada_str = f"R$ {total_entradas:,.2f}"
            gasto_str = f"R$ {total_gastos:,.2f}"
            balanco_valor_str = f"R$ {total_balanco:,.2f}"
            
            # 3. Montar a string principal com formatação Mathtext apenas para o Balanço
            # O r antes das aspas garante que a barra invertida (\) seja tratada literalmente.
            stats_text = (
                f"Resumo ({month_name.upper()}): Entradas: {entrada_str} | Saídas: {gasto_str} | Balanço: "
                # Utilizamos a sintaxe correta para negrito e cor no Mathtext
                r'$\bf{\color{%s}%s}$' % (color_name, balanco_valor_str)
            )

            # 4. Plotagem em um ÚNICO comando fig.text
            # O Matplotlib detecta o Mathtext no final da string e o renderiza.
            # usetex=False (padrão) é geralmente o que queremos para Mathtext.
            fig.text(0.02, 0.01, stats_text, 
                     ha='left', fontsize=9, color=self.colors['default'])
            
            # Texto de geração (permanece separado no canto direito)
            fig.text(0.98, 0.01, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                     ha='right', fontsize=8, color=self.colors['default'])
            
            fig.tight_layout(rect=[0, 0.03, 1, 0.96])


        # FIGURA 2: Página 2 do PDF (CONSOLIDADO FINANCEIRO)
        fig_page2 = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT), facecolor=self.colors['background'])
        
        # Grid: [1.0: Gastos Mensais, 1.0: Dívida, 1.0: Reserva] - 3 linhas!
        gs_page2 = gridspec.GridSpec(3, 1, figure=fig_page2, hspace=0.45, wspace=0.2, 
                                     height_ratios=[1.0, 1.0, 1.0])

        fig_page2.suptitle("RELATÓRIO FINANCEIRO - CONSOLIDADO", fontsize=16, fontweight='bold', color=self.colors['default'], y=0.98)
        
        # 1. Gastos Mensais (com comparação)
        ax_expense = fig_page2.add_subplot(gs_page2[0], facecolor=self.colors['secondary_bg'])
        self.create_monthly_expense_chart(fig_page2, ax_expense, data, current_year, current_month) 
        
        # 2. Dívida em Aberto
        ax_debt = fig_page2.add_subplot(gs_page2[1], facecolor=self.colors['secondary_bg'])
        self.create_debt_and_invoice_chart(fig_page2, ax_debt, data, current_year)
        
        # 3. Reserva
        ax_reserve = fig_page2.add_subplot(gs_page2[2], facecolor=self.colors['secondary_bg'])
        self.create_reserve_line_chart(fig_page2, ax_reserve, data)
        
        # Chamada da função de rodapé atualizada
        add_footer(fig_page2, total_entradas, total_gastos, total_balanco, month_name)

        return fig_page2

# --- CLASSE 2: HABIT TRACKER (Relatórios de Hábito) ---

# *******************************************************************
# A CLASSE HABIT TRACKER É MANTIDA EXATAMENTE COMO NA VERSÃO ANTERIOR
# PARA ATENDER AO REQUISITO "A primeira, permance iigual"
# *******************************************************************

class HabitTracker:
    """Gera o relatório visual de rastreamento de hábitos."""
    def __init__(self, supabase_url, supabase_key):
        self.supabase = create_client(supabase_url, supabase_key)
        self.colors = {
            'default': '#f0f6fc',
            'background': '#0d1117',
            'secondary_bg': '#161b22',
            'border': '#30363d',
            'level0': '#161b22', 
            'level1': '#0e4429', 
            'level2': '#006d32', 
            'level3': '#26a641', 
            'level4': '#39d353',
            'highlight': '#006d32'
        }
        self.font_size = 8

    def fetch_all_data(self):
        """Busca todos os hábitos e todos os registros."""
        try:
            print("Buscando dados de Hábitos do Supabase...")
            habits_response = self.supabase.table("habitos").select("*").eq("ativo", True).execute()
            habits = habits_response.data
            registros_response = self.supabase.table("habitos_registros").select("*").execute()
            registros = registros_response.data
            return habits, registros
        except Exception as e:
            print(f"Erro ao buscar todos os dados de hábito: {e}")
            return [], []

    def prepare_month_data(self, habits, registros, year, month):
        _, num_days = calendar.monthrange(year, month)
        habit_data = {}
        for habit in habits:
            habit_id = habit['id']
            calendar_dict = {datetime(year, month, day).date(): 0 for day in range(1, num_days + 1)}
            habit_registros = [r for r in registros if r['habito_id'] == habit_id]
            for registro in habit_registros:
                if isinstance(registro['data_registro'], str):
                    registro_date = datetime.strptime(registro['data_registro'], '%Y-%m-%d').date()
                else:
                    registro_date = registro['data_registro']
                if registro_date.year == year and registro_date.month == month:
                    calendar_dict[registro_date] = registro['nivel']
            habit_data[habit_id] = {'name': habit['nome'], 'calendar': calendar_dict}
        return habit_data, num_days

    def calculate_habit_rates(self, habits, all_registros, start_date, end_date):
        habit_rates = {}; delta = end_date - start_date
        total_days_in_period = delta.days + 1
        for habit in habits:
            habit_id = habit['id']
            filtered_registros = [
                r for r in all_registros 
                if r['habito_id'] == habit_id and 
                   start_date <= datetime.strptime(r['data_registro'], '%Y-%m-%d').date() <= end_date
            ]
            recorded_dates = {datetime.strptime(r['data_registro'], '%Y-%m-%d').date() for r in filtered_registros}
            total_completed_days = len(recorded_dates)
            rate = (total_completed_days / total_days_in_period * 100) if total_days_in_period > 0 else 0
            habit_rates[habit_id] = {'name': habit['nome'], 'rate': rate}
        return habit_rates
    
    def calculate_monthly_rates(self, habits, all_registros):
        today = datetime.now(); current_year = today.year
        monthly_rates_df = pd.DataFrame(index=[h['nome'] for h in habits])
        for month_num in range(1, 13):
            month_name = calendar.month_abbr[month_num]
            _, num_days = calendar.monthrange(current_year, month_num)
            start_date = datetime(current_year, month_num, 1).date()
            end_date = datetime(current_year, month_num, num_days).date()
            month_habit_rates = self.calculate_habit_rates(habits, all_registros, start_date, end_date)
            month_column = {habit['nome']: month_habit_rates.get(habit['id'], {'rate': 0})['rate'] for habit in habits}
            monthly_rates_df[month_name] = pd.Series(month_column)
        return monthly_rates_df

    def calculate_overall_monthly_rates(self, all_habits, all_registros):
        today = datetime.now(); current_year = today.year; overall_monthly_rates = {}
        for month_num in range(1, 13):
            month_name = calendar.month_abbr[month_num]
            _, num_days = calendar.monthrange(current_year, month_num)
            start_date = datetime(current_year, month_num, 1).date()
            end_date = datetime(current_year, month_num, num_days).date()
            registros_month = [r for r in all_registros if start_date <= datetime.strptime(r['data_registro'], '%Y-%m-%d').date() <= end_date]
            if not registros_month:
                overall_monthly_rates[month_name] = np.nan; continue
            total_possible_month = len(all_habits) * num_days
            habit_dates_completed = {habit['id']: set() for habit in all_habits}
            for reg in registros_month:
                habit_dates_completed[reg['habito_id']].add(datetime.strptime(reg['data_registro'], '%Y-%m-%d').date())
            total_completed_month = sum(len(dates) for dates in habit_dates_completed.values())
            rate = (total_completed_month / total_possible_month * 100) if total_possible_month > 0 else 0
            overall_monthly_rates[month_name] = rate
        return overall_monthly_rates

    def generate_overall_stats(self, habit_data, num_days, n_habits_total):
        """Gera estatísticas gerais"""
        total_possible = n_habits_total * num_days
        total_completed = sum(1 for habit in habit_data.values() for level in habit['calendar'].values() if level > 0)
        completion_rate = (total_completed / total_possible * 100) if total_possible > 0 else 0
        
        return (f"Total de Hábitos: {n_habits_total} | Dias no Mês: {num_days} | "
                f"Registros: {total_completed}/{total_possible} | Taxa Geral do Mês: {completion_rate:.1f}%")
    
    def create_summary_header(self, fig, gs_summary, stats_text, month_name):
        """Cria o Resumo Geral e o Título Principal."""
        ax = fig.add_subplot(gs_summary, facecolor=self.colors['background'])
        
        ax.set_title(f"RELATÓRIO DE HÁBITOS", fontsize=16, fontweight='bold', color=self.colors['default'], pad=20)
        
        ax.text(0.5, 0.45, stats_text, 
                fontsize=10, 
                ha='center', va='center', 
                color=self.colors['default'],
                bbox=dict(boxstyle="round,pad=0.4", facecolor=self.colors['secondary_bg'], edgecolor=self.colors['border']))
        
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_visible(False)
        return ax

    def create_compact_calendar(self, habit_data, year, month, num_days, fig, gs_calendar):
        """Cria o calendário compacto."""
        ax = fig.add_subplot(gs_calendar, facecolor=self.colors['background'])
        
        colors = {0: self.colors['level0'], 1: self.colors['level1'], 2: self.colors['level2'], 3: self.colors['level3'], 4: self.colors['level4']}
        n_habits = len(habit_data)
        square_size = 0.7
        name_width = 3.0 
        
        start_x = name_width
        start_y_offset = (n_habits + 2) * square_size
        
        for day_idx, day_num in enumerate(range(1, num_days + 1)):
            x_pos = start_x + (day_idx * square_size)
            ax.text(x_pos + square_size/2, start_y_offset, str(day_num), 
                   ha='center', va='center', fontsize=7, fontweight='bold', color=self.colors['default'])
        
        for habit_idx, (habit_id, habit) in enumerate(habit_data.items()):
            y_pos = start_y_offset - (habit_idx * square_size) - square_size
            
            ax.text(name_width - 0.2, y_pos + square_size/2, habit['name'], 
                   ha='right', va='center', fontsize=self.font_size, fontweight='bold', color=self.colors['default'])
            
            for day_idx in range(num_days):
                date = datetime(year, month, day_idx + 1).date()
                level = habit['calendar'].get(date, 0)
                color = colors.get(level, colors[0])
                x_pos = start_x + (day_idx * square_size)
                
                rect = patches.Rectangle((x_pos, y_pos), square_size - 0.05, square_size - 0.05, 
                                         linewidth=0.8, edgecolor=self.colors['border'], facecolor=color, joinstyle='round')
                ax.add_patch(rect)
        
        total_width = start_x + (num_days * square_size)
        ax.set_xlim(0, total_width)
        ax.set_ylim(0, start_y_offset + square_size)
        ax.set_aspect('equal')
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_visible(False)
        
        month_name = calendar.month_name[month]
        ax.set_title(f"Calendário - {month_name} {year}", 
                     fontsize=12, fontweight='bold', pad=10, color=self.colors['default'])
        
        legend_elements = [patches.Patch(facecolor=c, edgecolor=self.colors['border'], label=l) for c, l in 
                           zip([colors[i] for i in range(5)], ['Não feito', 'Nível 1', 'Nível 2', 'Nível 3', 'Nível 4+'])]
        
        ax.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.05),
                  ncol=5, frameon=True, facecolor=self.colors['secondary_bg'], edgecolor=self.colors['border'],
                  fontsize=self.font_size, labelcolor=self.colors['default'])
        
        return ax

    def create_ranking_section(self, fig, gs_ranking, habits, all_registros, year, month):
        """Cria a seção de ranking."""
        ax = fig.add_subplot(gs_ranking, facecolor=self.colors['secondary_bg'])
        ax.set_title("Ranking de Hábitos (Mês Atual)", fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)
        
        _, num_days = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, num_days).date()
        
        habit_rates = self.calculate_habit_rates(habits, all_registros, start_date, end_date)
        
        sorted_habits = sorted(habit_rates.values(), key=lambda x: x['rate'], reverse=True)
        
        y_pos = np.arange(len(sorted_habits))
        rates = [h['rate'] for h in sorted_habits]
        names = [h['name'] for h in sorted_habits]
        
        bar_colors = plt.cm.Greens(np.linspace(0.4, 0.9, len(sorted_habits)))
        
        bars = ax.barh(y_pos, rates, color=bar_colors[::-1])
        ax.set_yticks(y_pos, labels=names, color=self.colors['default'], fontsize=self.font_size)
        ax.set_xlabel("Taxa de Conclusão (%)", color=self.colors['default'], fontsize=self.font_size)
        ax.set_xlim(0, 100)
        ax.tick_params(axis='x', colors=self.colors['default'])
        
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 2, bar.get_y() + bar.get_height()/2, f'{width:.1f}%',
                    va='center', ha='left', color=self.colors['default'], fontsize=self.font_size - 1)

        ax.invert_yaxis()
        for spine in ax.spines.values(): spine.set_visible(False)
        ax.xaxis.grid(True, linestyle='--', alpha=0.3, color=self.colors['default'])
        
    def create_monthly_table(self, fig, gs_table, monthly_rates_df, current_month_num):
        """Cria a tabela de taxas mensais."""
        ax = fig.add_subplot(gs_table, facecolor=self.colors['secondary_bg'])
        ax.set_title("Taxa de Conclusão Mensal por Hábito (%)", 
                     fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)
        
        df_display = monthly_rates_df.applymap(lambda x: f"{x:.1f}%")
        habit_overall_rates = monthly_rates_df.mean(axis=1).apply(lambda x: f"{x:.1f}%")
        df_display['Geral'] = habit_overall_rates
        
        table = ax.table(cellText=df_display.values, colLabels=df_display.columns, 
                         rowLabels=df_display.index, loc='center', cellLoc='center')
        
        table.auto_set_font_size(False); table.set_fontsize(self.font_size); table.scale(1.0, 1.2)
        
        for (i, j), cell in table.get_celld().items():
            cell.set_edgecolor(self.colors['border']); cell.set_facecolor(self.colors['secondary_bg'])
            cell.set_text_props(color=self.colors['default'])
            
            if i == 0 or j == -1:
                cell.set_facecolor(self.colors['background']); cell.set_text_props(weight='bold', color=self.colors['default'])
            
            current_month_name = calendar.month_abbr[current_month_num]
            if j >= 0 and df_display.columns[j] == current_month_name:
                cell.set_facecolor(self.colors['highlight']); cell.set_text_props(weight='bold', color='white')
        
        ax.axis('off')

    def create_overall_monthly_chart(self, fig, gs_chart, overall_monthly_rates):
        """Cria o gráfico de linha com quebras para dados ausentes."""
        ax = fig.add_subplot(gs_chart, facecolor=self.colors['secondary_bg'])
        ax.set_title("Taxa Geral Mês a Mês (%)", fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)
        
        months = list(overall_monthly_rates.keys())
        rates = list(overall_monthly_rates.values())
        
        ax.plot(months, rates, marker='o', color=self.colors['level4'], linewidth=2, markersize=6)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Mês", color=self.colors['default'], fontsize=self.font_size)
        ax.set_ylabel("Taxa de Conclusão (%)", color=self.colors['default'], fontsize=self.font_size)
        
        ax.tick_params(axis='x', colors=self.colors['default'], rotation=0); ax.tick_params(axis='y', colors=self.colors['default'])
        ax.grid(True, linestyle='--', alpha=0.3, color=self.colors['default'])
        for spine in ax.spines.values(): spine.set_visible(False)
        
    def generate_figure(self):
        """Gera e retorna a figura completa do relatório de hábitos (Página 1)."""
        plt.style.use('dark_background')
        
        all_habits, all_registros = self.fetch_all_data()
        if not all_habits:
            print("Nenhum hábito ativo encontrado!"); return None
        
        # Usando a data atual
        today = datetime.now() 
        current_year, current_month = today.year, today.month
        month_name = calendar.month_name[current_month]

        current_month_habit_data, current_num_days = self.prepare_month_data(all_habits, all_registros, current_year, current_month)
        monthly_rates_df = self.calculate_monthly_rates(all_habits, all_registros)
        overall_monthly_rates = self.calculate_overall_monthly_rates(all_habits, all_registros)
        stats_text = self.generate_overall_stats(current_month_habit_data, current_num_days, len(all_habits))

        # Configuração do Layout - A4 (8.5x11 inches)
        FIG_WIDTH, FIG_HEIGHT = 8.5, 11.0 
        fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT), facecolor=self.colors['background'])
        
        n_habits = len(all_habits)
        CALENDAR_HEIGHT_RATIO = max(1.0, n_habits * 0.15 + 0.5) 
        
        # Grid: [0.3: Resumo, CALENDAR_HEIGHT_RATIO: Calendário, 0.7: Ranking, 1.2: Tabela, 0.8: Gráfico]
        gs = fig.add_gridspec(nrows=5, ncols=1, 
                              height_ratios=[0.3, CALENDAR_HEIGHT_RATIO, 0.7, 1.2, 0.8], 
                              hspace=0.6)
        
        # 1. Resumo Geral
        gs_summary = gs[0].subgridspec(1, 1)
        self.create_summary_header(fig, gs_summary[0], stats_text, month_name)
        
        # 2. Calendário
        self.create_compact_calendar(current_month_habit_data, current_year, current_month, current_num_days, fig, gs[1])
        
        # 3. Ranking
        gs_ranking = gs[2].subgridspec(1, 1, hspace=0)
        self.create_ranking_section(fig, gs_ranking[0], all_habits, all_registros, current_year, current_month)
        
        # 4. Tabela
        gs_table = gs[3].subgridspec(1, 1, hspace=0)
        self.create_monthly_table(fig, gs_table[0], monthly_rates_df, current_month)
        
        # 5. Gráfico
        gs_chart = gs[4].subgridspec(1, 1, hspace=0)
        self.create_overall_monthly_chart(fig, gs_chart[0], overall_monthly_rates)
        
        plt.figtext(0.98, 0.01, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ha='right', fontsize=8, color=self.colors['default'])
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.98])
        
        return fig


import os
import io
import pytz
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime, timedelta
from supabase import create_client, Client 
from PIL import Image 
from imageio.v3 import imread 


import os
import io
import pytz
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime, timedelta
from supabase import create_client, Client 
from PIL import Image 
from imageio.v3 import imread 


import os
import io
import pytz
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime, timedelta
from supabase import create_client, Client 
from PIL import Image 
from imageio.v3 import imread 


class WorkoutReport:
    """Gera gráficos e mapas visuais para rastreamento de treinos, focado em 4 períodos semanais."""
    
    MUSCLE_MASKS_DIR = "body_images_masks/" 
    
    LOCAL_TIMEZONE = 'America/Sao_Paulo'
    
    MUSCLE_NAME_MAP = {
        'Peitoral': 'peitoral', 'Deltóide': 'deltoides', 'Tríceps': 'triceps', 'Bíceps': 'biceps',
        'Antebraço': 'antebraco', 'Glúteos': 'gluteo', 'Quadríceps': 'quadriceps', 
        'Posterior de Coxa': 'posterior', 'Panturrilha': 'panturrilha', 'Lombar': 'lombar',
        'Adutores': 'adutores', 'Abdutores': 'abdutores', 'Dorsal': 'dorsal', 'Romboides': 'romboides', 
        'Core': 'core', 'Abdômen': 'core', 
        'Costas': 'dorsal', 'Trapézio': 'romboides', 'Cardio': None 
    }
    
    SERIES_LIMITS = {
        'peitoral':    {'fraca': 7,  'media': 14}, 'dorsal':      {'fraca': 8,  'media': 15}, 
        'romboides':   {'fraca': 8,  'media': 15}, 'quadriceps':  {'fraca': 8,  'media': 14},
        'posterior':   {'fraca': 6,  'media': 11}, 'gluteo':      {'fraca': 7,  'media': 14},
        'deltoides':   {'fraca': 7,  'media': 14}, 'biceps':      {'fraca': 5,  'media': 9},
        'triceps':     {'fraca': 5,  'media': 9},  'panturrilha': {'fraca': 7,  'media': 14},
        'core':        {'fraca': 7,  'media': 14}, 'adutores':    {'fraca': 5,  'media': 9}, 
        'abdutores':   {'fraca': 5,  'media': 9},  'antebraco':   {'fraca': 5,  'media': 9},
        'lombar':      {'fraca': 5,  'media': 9}, 
    }
    
    COLOR_MAP = {
        'fraca': '#2C7BB6', 'media': '#FFA500', 'alta': '#FF4500', 'cinza': '#30363d'   
    }

    # Constantes para Radar e Força
    RADAR_CATEGORIES = ['Peito', 'Ombros', 'Core', 'Costas', 'Pernas', 'Braços']
    NUM_CATEGORIES = len(RADAR_CATEGORIES)
    ANGLES = np.linspace(0, 2 * np.pi, NUM_CATEGORIES, endpoint=False).tolist()
    ANGLES += ANGLES[:1] 
    
    KEY_EXERCISES = [
        'Supino reto', 'Agachamento livre', 'Remada curvada', 'Push Press', 'Levantamento terra', 'Barra fixa'
    ]
    RANK_ORDER = ['F', 'E', 'E+', 'D', 'D+', 'C', 'C+', 'B', 'B+', 'A', 'A+', 'S', 'S+']

    # Mapeamento de cores para o ranking
    RANK_COLORS = {
        'F':  '#0A1A2F',  # Azul bem escuro, quase preto
        'E':  '#0E2C4F',  # Azul escuro
        'E+': '#12406F',  # Azul mais saturado
        'D':  '#175C9E',  # Azul médio-escuro
        'D+': '#1E6FC4',  # Azul mais vivo
        'C':  '#2582EA',  # Azul forte
        'C+': '#2C9CFF',  # Azul brilhante
        'B':  '#33B5FF',  # Azul mais intenso
        'B+': '#3CCAFF',  # Azul neon claro
        'A':  '#45DDFF',  # Azul neon
        'A+': '#4FF0FF',  # Azul ciano elétrico
        'S':  '#66FFFF',  # Azul muito luminoso, quase neon total
        'S+': '#00FFFF',  # Azul neon puro (ciano)
    }
    
    # NOVAS CONSTANTES HRR
    HRR_EXERCICIO_ID = 16 # ID do exercício "HRR" no banco
    
    # NOVO Mapeamento de Cores para HRR (Gradiente de Azul: Escuro -> Claro/Brilhante)
    HRR_THRESHOLDS = {
        'Excelente': {'min': 45, 'cor': '#C7E9EF'}, # Ciano Claro (Mais Brilhante)
        'Bom':       {'min': 30, 'max': 45, 'cor': '#9ACBE5'}, # Azul Ciano Médio
        'Mediano':   {'min': 20, 'max': 30, 'cor': '#609ECF'}, # Azul Médio
        'Ruim':      {'max': 20, 'cor': '#2C7BB6'} # Azul Escuro (Cor Radar/Volume)
    }


    
    def __init__(self, supabase_url, supabase_key):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        
        self.colors = {
            'default': '#f0f6fc',
            'background': '#0d1117',
            'secondary_bg': '#161b22',
            'border': '#30363d',
            'highlight': '#006d32', 
        }
        self.colors['radar_fill'] = self.COLOR_MAP['fraca'] # Azul escuro principal
        self.font_size = 9
        
        self.BODY_MAP_PATH = "body.png"
        
        try:
            self.supabase: Client = create_client(supabase_url, supabase_key)
        except Exception as e:
            print(f"❌ ERRO ao inicializar cliente Supabase: {e}")
            self.supabase = None 
        
        self.user_body_weight = self._fetch_user_body_weight()
        self.force_ranks_map = self._fetch_force_ranks_map()
        
        try:
            self.body_map_img = imread(self.BODY_MAP_PATH)
            self.base_map_img = imread(os.path.join(self.MUSCLE_MASKS_DIR, "fundo.png"))
        except FileNotFoundError as e:
            print(f"❌ ERRO: Imagem base não encontrada. {e}")
            self.body_map_img = None
            self.base_map_img = None
        
        self.masks_cache = self._load_muscle_masks()
        
    def _load_muscle_masks(self):
        """Carrega todas as máscaras pré-criadas em um cache."""
        mask_map = {}
        levels = {'f': 'fraca', 'm': 'media', 'a': 'alta'} 
        
        try:
            mask_files = [f for f in os.listdir(self.MUSCLE_MASKS_DIR) if f.endswith('.png') and f != "fundo.png"]
        except FileNotFoundError:
            print(f"❌ ERRO: Pasta de máscaras '{self.MUSCLE_MASKS_DIR}' não encontrada.")
            return {}

        for filename in mask_files:
            parts = filename.split('-')
            if len(parts) == 2:
                muscle_name = parts[0]
                level_code = parts[1].split('.')[0] 
                
                if level_code in levels:
                    level_name = levels[level_code]
                    filepath = os.path.join(self.MUSCLE_MASKS_DIR, filename)
                    
                    try:
                        mask_img = imread(filepath)
                        if mask_img.ndim == 3 and mask_img.shape[2] == 4:
                            if muscle_name not in mask_map:
                                mask_map[muscle_name] = {}
                            mask_map[muscle_name][level_name] = mask_img
                    except Exception as e:
                        print(f"❌ ERRO ao carregar {filename}: {e}")
                        
        return mask_map

    def fetch_data_for_four_weeks(self):
        """
        Busca dados para 4 janelas de 7 dias, incluindo 'peso', 'repeticoes', 'tempo' e 'nome'
        para os cálculos de Volume e Força.
        """
        if self.supabase is None:
            return []

        try:
            local_tz = pytz.timezone(self.LOCAL_TIMEZONE)
        except pytz.UnknownTimeZoneError:
            print(f"❌ ERRO: Fuso horário '{self.LOCAL_TIMEZONE}' é inválido. Usando UTC.")
            local_tz = pytz.utc
            
        today_local = datetime.now(local_tz) 
        
        windows = []
        for i in range(4):
            end_date = today_local - timedelta(days=7 * i)
            start_date = end_date - timedelta(days=7)
            windows.append({'start': start_date, 'end': end_date})
            
        windows.reverse() 

        data_minima_iso = windows[0]['start'].astimezone(pytz.utc).isoformat()
        
        try:
            response_ex = self.supabase.table('exercicios').select('id, nome, grupo_muscular_primario, grupos_musculares_secundarios').limit(500).execute()
            df_exercicios = pd.DataFrame(response_ex.data).rename(columns={'id': 'exercicio_id'})
            
            response_rt = self.supabase.table('registros_treino').select('id, data_treino').gte('data_treino', data_minima_iso).execute()
            df_rt = pd.DataFrame(response_rt.data).rename(columns={'id': 'registro_treino_id'})
            
            if df_rt.empty or df_exercicios.empty:
                return []

            treino_ids = df_rt['registro_treino_id'].tolist()
            response_reg = self.supabase.table('registro_exercicios').select('registro_treino_id, exercicio_id, peso, repeticoes, tempo').in_('registro_treino_id', treino_ids).execute()
            df_registros = pd.DataFrame(response_reg.data)
            
            df_full = df_registros.merge(df_rt, on='registro_treino_id')
            df_full['data_treino'] = pd.to_datetime(df_full['data_treino'])
            df_full = df_full.merge(df_exercicios, on='exercicio_id')
            
            df_full['data_treino'] = df_full['data_treino'].dt.tz_convert(local_tz)

            weekly_data_sets = []
            for window in windows:
                df_window = df_full[(df_full['data_treino'] >= window['start']) & (df_full['data_treino'] <= window['end'])].copy()
                
                df_sets_in_period = df_window.copy()
                
                weekly_data_sets.append({
                    'start_date': window['start'].strftime('%d/%m'),
                    'end_date': window['end'].strftime('%d/%m'),
                    'data_sets': df_sets_in_period
                })
                
            return weekly_data_sets

        except Exception as e:
            print(f"❌ ERRO ao buscar dados semanais do Supabase: {e}")
            return []

    def calculate_muscle_series_weekly(self, df_sets):
        """Calcula o total de séries semanais por grupo muscular (1 série Primário, 0.5 série Secundário)."""
        
        if df_sets.empty:
            return {}

        df_sets['series_set'] = 1
        series_por_exercicio = df_sets.groupby('exercicio_id')['series_set'].sum()
        muscle_series_total = {}
        
        df_exercicios_unique = df_sets.drop_duplicates(subset=['exercicio_id'])
        
        for exercicio_id, total_series in series_por_exercicio.items():
            
            ex_row = df_exercicios_unique[df_exercicios_unique['exercicio_id'] == exercicio_id].iloc[0]

            primary_muscle_db = ex_row['grupo_muscular_primario']
            primary_muscle_key = self.MUSCLE_NAME_MAP.get(primary_muscle_db)
            
            if primary_muscle_key:
                muscle_series_total[primary_muscle_key] = muscle_series_total.get(primary_muscle_key, 0) + total_series
            
            secondary_muscles_db = ex_row['grupos_musculares_secundarios']
            if isinstance(secondary_muscles_db, list) and secondary_muscles_db:
                secondary_series = total_series * 0.5
                for secondary_db in secondary_muscles_db:
                    secondary_key = self.MUSCLE_NAME_MAP.get(secondary_db)
                    
                    if secondary_key:
                        muscle_series_total[secondary_key] = muscle_series_total.get(secondary_key, 0) + secondary_series
        
        return muscle_series_total
    
    def generate_heatmap_overlay(self, muscle_series_total):
        """
        Gera a sobreposição de calor, preservando as cores originais das máscaras.
        """
        if self.body_map_img is None or not self.masks_cache:
            return None

        overlay_img = np.zeros((*self.body_map_img.shape[:2], 4), dtype=np.uint8)

        for muscle_name_key, total_series in muscle_series_total.items():
            
            if total_series == 0 or muscle_name_key not in self.SERIES_LIMITS:
                continue
            
            limits = self.SERIES_LIMITS[muscle_name_key]
            level_name = None
            
            if total_series > limits['media']:
                level_name = 'alta'
            elif total_series > limits['fraca']:
                level_name = 'media'
            elif total_series > 0:
                level_name = 'fraca'

            if level_name:
                mask = self.masks_cache.get(muscle_name_key, {}).get(level_name)
                
                if mask is not None:
                    mask_alpha_channel = mask[:, :, 3] > 0
                    overlay_img[mask_alpha_channel] = mask[mask_alpha_channel]

        return overlay_img

    def create_body_map_comparison(self, fig, gs_body_maps, weekly_data_sets):
        """
        Gráfico 1: Plota 4 mapas corporais lado a lado, cada um representando o estímulo de uma semana.
        """
        
        ax_container = fig.add_subplot(gs_body_maps, facecolor=self.colors['secondary_bg'])
        
        ax_container.set_title("1. Comparativo de Estímulo Semanal de Grupos Musculares (Últimas 4 Semanas)", 
                                   fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)
        
        ax_container.set_xticks([]); ax_container.set_yticks([]); ax_container.axis('off')

        if self.body_map_img is None:
            ax_container.text(0.5, 0.5, "Imagem 'body.jpg' não encontrada. Verifique o caminho.", 
                              ha='center', va='center', color=self.colors['default'], transform=ax_container.transAxes)
            return

        gs_inner = gridspec.GridSpecFromSubplotSpec(1, 4, subplot_spec=gs_body_maps, 
                                                    wspace=0.1, hspace=0.1)
        
        comparison_titles = ["Semana 4", "Semana 3", "Semana 2", "Semana 1 (Atual)"]
        
        for i in range(4):
            ax_sub = fig.add_subplot(gs_inner[0, i]) 
            ax_sub.set_facecolor(self.colors['secondary_bg'])

            title = comparison_titles[i]
            overlay = None
            
            if i < len(weekly_data_sets):
                week_data = weekly_data_sets[i]
                
                title = f"{comparison_titles[i]}\n({week_data['start_date']} - {week_data['end_date']})"
                
                muscle_series = self.calculate_muscle_series_weekly(week_data['data_sets'])
                overlay = self.generate_heatmap_overlay(muscle_series)

            if self.base_map_img is not None:
                ax_sub.imshow(self.base_map_img, aspect='equal')
            else:
                ax_sub.imshow(self.body_map_img, aspect='equal')

            if overlay is not None:
                ax_sub.imshow(overlay, aspect='equal')
            
            ax_sub.set_title(title, fontsize=8, color=self.colors['default'], pad=5)
            ax_sub.axis('off')

    # Funções de Volume e Força (Gráfico 2)
    def _fetch_user_body_weight(self):
        """Busca o último peso corporal registrado do usuário."""
        if self.supabase is None: return 75.0 
        
        try:
            response = self.supabase.table('peso_corporal').select('peso_kg').order('data_registro', desc=True).limit(1).execute()
            
            if response.data and response.data[0]['peso_kg'] is not None:
                return float(response.data[0]['peso_kg'])
            
            return 75.0
            
        except Exception as e:
            print(f"❌ ERRO ao buscar peso corporal: {e}. Usando 75.0 kg.")
            return 75.0

    def _fetch_force_ranks_map(self):
        """Busca a matriz de ranks de força do banco de dados e monta o dicionário."""
        if self.supabase is None: return {}
        
        try:
            response = self.supabase.table('configuracao_rank_forca').select('nome_exercicio, rank_nome, multiplo_pc').execute()
            
            rank_map = {}
            for row in response.data:
                ex_name = row['nome_exercicio']
                rank_name = row['rank_nome']
                multiplo = float(row['multiplo_pc'])
                
                if ex_name not in rank_map:
                    rank_map[ex_name] = {}
                
                rank_map[ex_name][rank_name] = multiplo
                
            return rank_map
            
        except Exception as e:
            print(f"❌ ERRO ao buscar configuração de ranks: {e}. Usando dados simulados.")
            return {
                'Supino reto': {'F': 0.0, 'E': 0.5, 'C': 1.0, 'A': 1.5},
                'Agachamento livre': {'F': 0.0, 'E': 0.7, 'C': 1.3, 'A': 2.0},
                'Levantamento terra': {'F': 0.0, 'E': 0.8, 'C': 1.6, 'A': 2.5},
                'Remada curvada': {'F': 0.0, 'E': 0.4, 'C': 0.8, 'A': 1.2},
                'Push Press': {'F': 0.0, 'E': 0.3, 'C': 0.6, 'A': 0.9},
                'Barra fixa': {'F': 0.0, 'E': 3, 'C': 8, 'A': 15}, # Contagem de Reps
            }
            
    def _get_rank_for_lift(self, exercise_name, max_rep_value):
        """Calcula o Rank (F a S+) baseado no valor (Max Load ou Reps) e no PC."""
        
        target_multipliers = self.force_ranks_map.get(exercise_name, {})
        current_rank = 'F'
        
        if not target_multipliers: return current_rank

        if exercise_name == 'Barra fixa':
            base_value = max_rep_value 
            
        else:
            pc = self.user_body_weight
            base_value = max_rep_value / pc if pc > 0 else 0 

        # Itera sobre os ranks em ordem crescente para encontrar o maior rank atingido
        for rank in self.RANK_ORDER:
            multiplo_piso = target_multipliers.get(rank, None)
            
            if multiplo_piso is not None and base_value >= multiplo_piso:
                current_rank = rank
            # Se chegamos a um rank onde o valor está abaixo do piso, paramos.
            # (Assumindo que os múltiplos_piso estão em ordem crescente)
            elif multiplo_piso is not None and base_value < multiplo_piso:
                break
                
        return current_rank

    def calculate_max_load_and_rank(self, weekly_data_sets):
        """
        Calcula o maior Peso (Max Load) nos últimos 28 dias para os exercícios chave.
        """
        
        all_series_data = pd.concat([w['data_sets'] for w in weekly_data_sets if not w['data_sets'].empty])
        if all_series_data.empty: return []

        df_key_lifts = all_series_data[all_series_data['nome'].isin(self.KEY_EXERCISES)].copy()
        
        if df_key_lifts.empty: return []

        df_key_lifts['peso_num'] = pd.to_numeric(df_key_lifts['peso'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0).astype(float)
        df_key_lifts['repeticoes_num'] = pd.to_numeric(df_key_lifts['repeticoes'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).astype(int)

        df_key_lifts_valid = df_key_lifts[
            (df_key_lifts['peso_num'] > 0) & 
            (df_key_lifts['repeticoes_num'] > 0)
        ].copy()

        max_results = []
        
        for ex_name_db in self.KEY_EXERCISES:
            df_ex = df_key_lifts_valid[df_key_lifts_valid['nome'] == ex_name_db]
            
            if ex_name_db == 'Barra fixa':
                 df_bar_fixa_sem_peso = df_key_lifts[
                     (df_key_lifts['nome'] == 'Barra fixa') & 
                     (df_key_lifts['peso_num'] <= 5.0) &
                     (df_key_lifts['repeticoes_num'] > 0)
                 ]
                 if not df_bar_fixa_sem_peso.empty:
                      max_reps = df_bar_fixa_sem_peso['repeticoes_num'].max()
                      max_results.append({
                           'nome': 'Barra fixa', 
                           'max_value': float(max_reps), 
                           'rank': self._get_rank_for_lift('Barra fixa', max_reps)
                      })
                      continue 

            if not df_ex.empty:
                 max_load = df_ex['peso_num'].max()
                 
                 if max_load > 0:
                      max_results.append({
                           'nome': ex_name_db, 
                           'max_value': max_load, 
                           'rank': self._get_rank_for_lift(ex_name_db, max_load) 
                      })
                 else:
                      max_results.append({'nome': ex_name_db, 'max_value': 0.0, 'rank': 'F'})
            else:
                 max_results.append({'nome': ex_name_db, 'max_value': 0.0, 'rank': 'F'})

        for res in max_results:
            if res['nome'] == 'Levantamento terra': res['nome'] = 'Terra'
            elif res['nome'] == 'Agachamento livre': res['nome'] = 'Agachamento'
            elif res['nome'] == 'Remada curvada': res['nome'] = 'Remada curv.'
            elif res['nome'] == 'Supino reto': res['nome'] = 'Supino'
                
        return max_results

    def calculate_volume_load_weekly(self, weekly_data_sets):
        """
        Calcula o Volume-Carga semanal simples (Peso x Reps x Séries)
        e o atribui 100% ao grupo muscular Primário.
        """
        all_series_data = pd.concat([w['data_sets'] for w in weekly_data_sets if not w['data_sets'].empty])
        if all_series_data.empty: return {}
        
        df_sets = all_series_data.copy()

        df_sets['peso_num'] = pd.to_numeric(df_sets['peso'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0).astype(float)
        df_sets['repeticoes_num'] = pd.to_numeric(df_sets['repeticoes'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).astype(int)
        df_sets['tempo_num'] = pd.to_numeric(df_sets['tempo'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).astype(float) 

        df_sets['volume_load'] = np.where(
            df_sets['repeticoes_num'] > 0, 
            df_sets['repeticoes_num'] * df_sets['peso_num'],
            df_sets['tempo_num'] * df_sets['peso_num']
        )
        
        volume_por_exercicio = df_sets.groupby('exercicio_id')['volume_load'].sum()

        muscle_volume_total = {}
        df_exercicios_unique = df_sets.drop_duplicates(subset=['exercicio_id'])
            
        for exercicio_id, total_volume in volume_por_exercicio.items():
            if exercicio_id not in df_exercicios_unique['exercicio_id'].values: continue
            
            ex_row = df_exercicios_unique[df_exercicios_unique['exercicio_id'] == exercicio_id].iloc[0]
            primary_muscle_db = ex_row['grupo_muscular_primario']
            primary_muscle_key = self.MUSCLE_NAME_MAP.get(primary_muscle_db)
            
            if primary_muscle_key and primary_muscle_key != 'cardio':
                muscle_volume_total[primary_muscle_key] = muscle_volume_total.get(primary_muscle_key, 0) + total_volume
                
        return muscle_volume_total
    
    def _create_radar_chart(self, title, max_volume, volume_data={}, color=None):
        """Cria um gráfico de radar (hexagonal) preenchido com volume_data."""
        if color is None: color = self.colors['radar_fill']
        
        values = []
        radar_values_map = {}
        
        val_peito = volume_data.get('peitoral', 0)
        values.append(val_peito)
        radar_values_map['Peito'] = val_peito
        
        val_ombros = volume_data.get('deltoides', 0)
        values.append(val_ombros)
        radar_values_map['Ombros'] = val_ombros
        
        val_core = volume_data.get('core', 0) + volume_data.get('adutores', 0) + volume_data.get('abdutores', 0)
        values.append(val_core) 
        radar_values_map['Core'] = val_core
        
        val_costas = volume_data.get('dorsal', 0) + volume_data.get('romboides', 0) + volume_data.get('lombar', 0)
        values.append(val_costas)
        radar_values_map['Costas'] = val_costas
        
        val_pernas = volume_data.get('quadriceps', 0) + volume_data.get('posterior', 0) + volume_data.get('gluteo', 0) + volume_data.get('panturrilha', 0) 
        values.append(val_pernas)
        radar_values_map['Pernas'] = val_pernas
        
        val_bracos = volume_data.get('biceps', 0) + volume_data.get('triceps', 0) + volume_data.get('antebraco', 0) 
        values.append(val_bracos) 
        radar_values_map['Braços'] = val_bracos
            
        values += values[:1] 
        
        fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True), facecolor=self.colors['secondary_bg'])
        
        if sum(values) > 0:
            ax.plot(self.ANGLES, values, color=color, linewidth=2, linestyle='solid') 
            ax.fill(self.ANGLES, values, color=color, alpha=0.25) 
        
        ax.set_xticks(self.ANGLES[:-1])
        ax.set_xticklabels(self.RADAR_CATEGORIES, color=self.colors['default'], size=9)
        
        r_ticks = np.linspace(0, max_volume, 6)
        ax.set_yticks(r_ticks) 
        
        def format_volume(vol):
            if vol >= 1000000: return f"{vol/1000000:.0f}M kg"
            if vol >= 1000: return f"{vol/1000:.0f}k kg"
            return f"{int(vol)} kg"

        tick_labels = [""] * 5 + [format_volume(max_volume)]
        ax.set_yticklabels(tick_labels, color="grey", size=8) 
        
        ax.set_ylim(0, max_volume) 
        ax.set_rlabel_position(0)
        ax.grid(color=self.colors['border'], alpha=0.5)
        ax.spines['polar'].set_color(self.colors['border'])
        ax.set_title(title, va='bottom', color=self.colors['default'], size=10, pad=5)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.1, transparent=True, dpi=300) 
        plt.close(fig)
        buf.seek(0)
        
        return Image.open(buf), radar_values_map
        
    def _plot_volume_summary_table(self, ax, radar_values_map):
        """
        Plota uma tabela de resumo de valores ao lado do radar.
        """
        ax.axis('off')
        ax.set_facecolor(self.colors['secondary_bg'])
        
        # Limpar o eixo X e Y completamente
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_xlabel(""); ax.set_ylabel("")
        
        ax.text(0.5, 0.95, "Volume (Últimas 28 dias)", 
                ha='center', va='top', fontsize=10, fontweight='bold', color=self.colors['default'])
        
        table_data = []
        for category in self.RADAR_CATEGORIES:
            volume = radar_values_map.get(category, 0)
            
            if volume >= 1000000:
                vol_str = f"{volume/1000000:.2f}M kg"
            elif volume >= 1000:
                vol_str = f"{volume/1000:.2f}k kg"
            else:
                vol_str = f"{volume:.0f} kg"
                
            table_data.append([category, vol_str])
            
        # Ambos os rótulos de coluna vazios para remover "Eixo"
        table = ax.table(cellText=table_data, 
                         colLabels=["", ""], 
                         loc='center', 
                         cellLoc='left',
                         colColours=[self.colors['secondary_bg']]*2, 
                         cellColours=[[self.colors['secondary_bg']]*2]*len(table_data)
                         )
                         
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.5) 

        for i in range(len(table_data)):
            table[(i+1, 0)].get_text().set_color(self.colors['default']) 
            table[(i+1, 1)].get_text().set_color(self.colors['radar_fill']) 
            table[(i+1, 1)].set_text_props(ha='right') 
            
        # Limpa o texto dos rótulos de cabeçalho
        for j in range(2):
            table[(0, j)].get_text().set_color(self.colors['default'])
            table[(0, j)].get_text().set_text('') 
        table[(0, 1)].set_text_props(ha='right')
        
    def _plot_force_rank_table_internal(self, ax, force_rank_data):
        """
        Plota a tabela de Max Load (Peso Máximo) e Ranks.
        """
        ax.axis('off')
        ax.set_facecolor(self.colors['secondary_bg'])
        
        ax.text(0.5, 0.95, "Força Máxima (Max Load/Reps)", 
                ha='center', va='top', fontsize=10, fontweight='bold', color=self.colors['default'])
        
        table_data = []
        
        ordered_data = {item['nome']: item for item in force_rank_data}
        ordered_list = [ordered_data.get(name, {'nome': name, 'max_value': 0.0, 'rank': 'F'}) 
                        for name in ['Supino', 'Agachamento', 'Remada curv.', 'Push Press', 'Terra', 'Barra fixa']]
        
        for item in ordered_list:
            max_value = item['max_value']
            ex_name = item['nome']
            
            if ex_name == 'Barra fixa':
                vol_str = f"{max_value:.0f} Reps" if max_value > 0 else "N/A"
            else:
                if max_value >= 1000:
                    vol_str = f"{max_value/1000:.1f}k kg"
                elif max_value > 0:
                    vol_str = f"{max_value:.1f} kg"
                else:
                    vol_str = "N/A"
            
            table_data.append([ex_name, vol_str, item['rank']])
            
        table = ax.table(cellText=table_data, 
                         colLabels=["Exercício", "Max", "Rank"], 
                         loc='center', 
                         cellLoc='left',
                         colColours=[self.colors['secondary_bg']]*3, 
                         cellColours=[[self.colors['secondary_bg']]*3]*len(table_data)
                         )
                         
        table.auto_set_font_size(False)
        table.set_fontsize(7.5) 
        table.scale(1, 1.25) 

        for i in range(len(table_data)):
            table[(i+1, 0)].get_text().set_color(self.colors['default']) 
            
            # Cor da coluna Max alterada para azul (radar_fill)
            table[(i+1, 1)].get_text().set_color(self.colors['radar_fill']) 
            
            table[(i+1, 1)].set_text_props(ha='right') 
            
            # APLICAÇÃO DO GRADIENTE DE COR DO RANK:
            rank_text = table_data[i][2] 
            color_for_rank = self.RANK_COLORS.get(rank_text, self.colors['default']) 
            table[(i+1, 2)].get_text().set_color(color_for_rank) 
            table[(i+1, 2)].set_text_props(ha='center')
            
        for j in range(3):
            table[(0, j)].get_text().set_color(self.colors['default'])
        table[(0, 1)].set_text_props(ha='right')
        table[(0, 2)].set_text_props(ha='center')

    def create_volume_radar_charts(self, fig, gs_volume_charts, weekly_volume_data, weekly_data_sets):
        """Gráfico 2: Plota o Radar, Tabela de Volume e Tabela de Força juntos."""
        
        total_volume_data = weekly_volume_data
        max_volume = 10000 
        consolidated_volumes = []
        consolidated_volumes.append(total_volume_data.get('peitoral', 0))
        consolidated_volumes.append(total_volume_data.get('deltoides', 0))
        consolidated_volumes.append(total_volume_data.get('core', 0) + total_volume_data.get('adutores', 0) + total_volume_data.get('abdutores', 0)) 
        consolidated_volumes.append(total_volume_data.get('dorsal', 0) + total_volume_data.get('romboides', 0) + total_volume_data.get('lombar', 0))
        consolidated_volumes.append(total_volume_data.get('quadriceps', 0) + total_volume_data.get('posterior', 0) + total_volume_data.get('gluteo', 0) + total_volume_data.get('panturrilha', 0))
        consolidated_volumes.append(total_volume_data.get('biceps', 0) + total_volume_data.get('triceps', 0) + total_volume_data.get('antebraco', 0))

        if consolidated_volumes:
            max_volume_data = max(consolidated_volumes)
            max_volume = np.ceil(max_volume_data / 5000) * 5000
            max_volume = max(10000, max_volume)

        radar_img, radar_values_map = self._create_radar_chart(title="Volume Mensal Consolidado", 
                                                         max_volume=max_volume, 
                                                         volume_data=total_volume_data,
                                                         color=self.colors['radar_fill'])
        
        force_rank_data = self.calculate_max_load_and_rank(weekly_data_sets)
        
        ax_container = fig.add_subplot(gs_volume_charts, facecolor=self.colors['secondary_bg'])
        ax_container.set_title("2. Volume e Força (Últimas 4 Semanas)", 
                     fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)
        ax_container.set_xticks([]); ax_container.set_yticks([]); ax_container.axis('off')

        gs_inner = gridspec.GridSpecFromSubplotSpec(1, 3, subplot_spec=gs_volume_charts, 
                                                    wspace=0.1, hspace=0.1,
                                                    width_ratios=[1.2, 0.8, 1.0]) 
        
        # Subplot 1: Radar
        ax_radar = fig.add_subplot(gs_inner[0, 0])
        ax_radar.imshow(radar_img, aspect='equal')
        ax_radar.axis('off')

        # Subplot 2: Tabela de Volume
        ax_table_volume = fig.add_subplot(gs_inner[0, 1])
        self._plot_volume_summary_table(ax_table_volume, radar_values_map)

        # Subplot 3: Tabela de Força 
        ax_table_force = fig.add_subplot(gs_inner[0, 2])
        self._plot_force_rank_table_internal(ax_table_force, force_rank_data) 

    # NOVO: Funções HRR
    def _fetch_hrr_weekly_average(self, weekly_data_sets):
        """
        Calcula a média de HRR por semana a partir dos dados brutos.
        O valor do HRR é armazenado em 'repeticoes' para o exercício ID 16.
        """
        hrr_data = []
        
        for i, week_data in enumerate(weekly_data_sets):
            df_sets = week_data['data_sets']
            
            # Filtra apenas o exercício HRR (ID 16)
            df_hrr = df_sets[df_sets['exercicio_id'] == self.HRR_EXERCICIO_ID].copy()
            
            # O valor do HRR é armazenado em 'repeticoes'
            df_hrr['hrr_value'] = pd.to_numeric(
                df_hrr['repeticoes'].astype(str).str.replace(',', '.'), 
                errors='coerce'
            ).fillna(0).astype(int)
            
            # Filtra registros com valor de HRR válido (maior que zero)
            df_hrr = df_hrr[df_hrr['hrr_value'] > 0]
            
            # Calcula a média semanal
            weekly_average = df_hrr['hrr_value'].mean() if not df_hrr.empty else 0
            
            hrr_data.append({
                'label': f"S{i+1}\n({week_data['start_date']})",
                'average_hrr': weekly_average
            })
            
        return hrr_data
        
    def _plot_hrr_line_chart(self, fig, ax, hrr_data):
        """
        Gráfico 3: Plota o HRR médio semanal com zonas de referência.
        Utilizando o gradiente de azul solicitado.
        """
        ax.set_title("3. Média Semanal de Recuperação da Frequência Cardíaca (HRR)", 
                     fontsize=12, fontweight='bold', color=self.colors['default'], pad=10)
        ax.set_facecolor(self.colors['secondary_bg'])
        
        labels = [d['label'] for d in hrr_data]
        values = [d['average_hrr'] for d in hrr_data]
        
        # 1. Plotar as Zonas de Referência (HRR_THRESHOLDS)
        current_y_min = 0 
        max_y_data = max(values) * 1.1 if values and max(values) > 0 else 60
        max_threshold = max([l.get('min', 0) for l in self.HRR_THRESHOLDS.values()] + [l.get('max', 0) for l in self.HRR_THRESHOLDS.values()])
        ax.set_ylim(0, max(max_y_data, max_threshold * 1.1)) 

        # Inverter a ordem para desenhar de baixo (Ruim/Escuro) para cima (Excelente/Claro)
        sorted_thresholds = sorted(self.HRR_THRESHOLDS.items(), key=lambda item: item[1].get('min', 0))
        
        # Desenhar Zonas e Linhas
        for level, limits in sorted_thresholds:
            
            y_max = limits.get('max', ax.get_ylim()[1]) 
            y_min = limits.get('min', current_y_min)
            
            # Ajuste de limites para as zonas de extremidade (garantindo que cobrem a área correta)
            if level == 'Excelente':
                y_min = limits['min']
                y_max = ax.get_ylim()[1]
            elif level == 'Ruim':
                y_max = limits['max']
                y_min = 0

            # Desenha o background da zona com a cor do gradiente de azul
            zone_color = limits['cor']
            ax.axhspan(y_min, y_max, facecolor=zone_color, alpha=0.15, zorder=0)

            # Desenha a linha pontilhada (limite inferior da zona, exceto para 'Ruim')
            if 'min' in limits and limits['min'] > 0:
                 # Usa uma versão mais escura da cor para a linha de separação
                 ax.axhline(limits['min'], color=zone_color, linestyle='--', linewidth=1.0, alpha=0.9, zorder=1)
            
            # Adiciona o rótulo da zona (ajustando a posição vertical)
            # Usa a cor da zona para o texto
            if len(labels) > 0:
                text_y = y_max - (y_max - y_min) * 0.25 
                if level == 'Ruim': text_y = y_max * 0.5
                
                ax.text(len(labels) - 0.5, text_y, f"{level}", 
                        ha='right', va='center', fontsize=8, color=zone_color, fontweight='bold', alpha=0.9)
                
            current_y_min = y_max

        # Configurar Eixos
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, color=self.colors['default'], fontsize=8)
        ax.set_xlabel("Média Semanal", color=self.colors['default'], labelpad=10)
        ax.set_ylabel("HRR (Batimentos/min)", color=self.colors['default'], labelpad=10)
        
        # 2. Plotar a Linha do HRR
        if any(v > 0 for v in values):
            
            # Linha principal - usa o azul escuro padrão para manter a consistência com o radar
            ax.plot(values, color=self.colors['radar_fill'], marker='o', linewidth=2, linestyle='-', markersize=6, zorder=3)
            
            # Adicionar rótulos de valor em cima dos pontos
            for x, y in enumerate(values):
                if y > 0:
                    ax.text(x, y + 1, f"{y:.1f}", ha='center', va='bottom', fontsize=7, color=self.colors['default'], fontweight='bold', zorder=4)

        ax.tick_params(axis='y', colors=self.colors['default'], labelsize=8)
        ax.grid(axis='y', color=self.colors['border'], linestyle='-', alpha=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color(self.colors['border'])
        ax.spines['left'].set_color(self.colors['border'])

    def generate_figure(self):
        """Gera a figura completa do relatório de treino (Página 3)."""
        plt.style.use('dark_background')
        
        FIG_WIDTH, FIG_HEIGHT = 8.5, 11.0 
        fig_page3 = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT), facecolor=self.colors['background'], dpi=300) 
        
        weekly_data_sets = self.fetch_data_for_four_weeks()
        
        gs_page3 = gridspec.GridSpec(3, 1, figure=fig_page3, 
                                     hspace=0.45, wspace=0.2, 
                                     height_ratios=[1.6, 1.0, 1.0],
                                     left=0.05, 
                                     right=0.95 
                                     ) 

        fig_page3.suptitle("RELATÓRIO DE TREINO - PROGRESSÃO", 
                          fontsize=16, fontweight='bold', color=self.colors['default'], y=0.98)
        
        # 1. Heatmap
        self.create_body_map_comparison(fig_page3, gs_page3[0], weekly_data_sets)
        
        # 2. Volume e Força
        weekly_volume_data = self.calculate_volume_load_weekly(weekly_data_sets)
        self.create_volume_radar_charts(fig_page3, gs_page3[1], weekly_volume_data, weekly_data_sets)
        
        # 3. Gráfico de HRR 
        hrr_data = self._fetch_hrr_weekly_average(weekly_data_sets)
        ax_hrr = fig_page3.add_subplot(gs_page3[2], facecolor=self.colors['secondary_bg'])
        self._plot_hrr_line_chart(fig_page3, ax_hrr, hrr_data)
        
        plt.figtext(0.98, 0.01, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ha='right', fontsize=8, color=self.colors['default'])
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.96])

        return fig_page3

# --- CLASSE 3: MASTER REPORT GENERATOR (Orquestrador e Gerador de PDF) ---
class MasterReportGenerator:
    """Orquestra a geração dos relatórios de Finanças, Hábitos e Treino e os salva em um único PDF."""
    def __init__(self, supabase_url, supabase_key):
        self.SUPABASE_URL = supabase_url
        self.SUPABASE_KEY = supabase_key

    def generate_all_reports(self, output_filename="Relatorio_Geral_Consolidado.pdf"):
        plt.style.use('dark_background')
        
        # 1. Instanciar e buscar dados
        finance_reporter = FinanceReport(self.SUPABASE_URL, self.SUPABASE_KEY)
        habit_tracker = HabitTracker(self.SUPABASE_URL, self.SUPABASE_KEY)
        workout_reporter = WorkoutReport(self.SUPABASE_URL, self.SUPABASE_KEY) # NOVA INSTANCIA
        
        finance_data = finance_reporter.fetch_all_data()
        
        if not finance_data:
            print("❌ Falha ao buscar dados financeiros. Abortando geração do PDF.")
            # Continuamos se for apenas um erro, mas para o FinanceReport, vamos parar por ser um dos principais
            # Poderíamos fazer um try/except mais robusto aqui, mas seguiremos a lógica atual.
            return

        # 2. Gerar Figuras (Figuras em si, sem salvar)
        print("✅ Gerando figura do Relatório de Hábitos (Página 1)...")
        fig_habit = habit_tracker.generate_figure()

        print("✅ Gerando figura do Relatório Financeiro (Página 2)...")
        fig_finance = finance_reporter.generate_finance_page(finance_data)
        
        print("✅ Gerando figura do Relatório de Treino (Página 3)...")
        fig_workout = workout_reporter.generate_figure() # NOVA CHAMADA
        
        # 3. Salvar tudo em um único PDF
        print(f"📄 Salvando figuras no arquivo PDF: {output_filename}")
        
        figures_to_save = []
        if fig_habit:
            figures_to_save.append(fig_habit) # Página 1: Hábitos
        figures_to_save.append(fig_finance) # Página 2: Consolidado Financeiro
        if fig_workout:
            figures_to_save.append(fig_workout) # Página 3: Treino (NOVA)

        with PdfPages(output_filename) as pdf:
            for fig in figures_to_save:
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)

        print(f"✨ Sucesso! O arquivo '{output_filename}' foi gerado com {len(figures_to_save)} páginas.")




# --- Bloco de Execução Principal ---
if __name__ == "__main__":

    
    # SUPABASE_URL = os.getenv("SUPABASE_URL")
    # SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_URL = "https://pnwkvrfshrthgtujmnkv.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBud2t2cmZzaHJ0aGd0dWptbmt2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA1NDgyNDksImV4cCI6MjA3NjEyNDI0OX0.NyYFRbz81kJsXLXJJc9X92NVM_Zg-K29A2JuufnbWxA"


    # Criar e executar o gerador mestre
    master_generator = MasterReportGenerator(SUPABASE_URL, SUPABASE_KEY)
    master_generator.generate_all_reports()

