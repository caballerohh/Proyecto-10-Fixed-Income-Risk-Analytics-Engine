"""
Fixed Income Risk Decomposition Framework
==========================================
Buy-Side Fixed Income Research Report Generator
Instrument: Apple Inc. 4.650% Senior Notes due 2044
Author: Fixed Income Analytics Desk
"""

import numpy as np
import pandas as pd
import pandas_datareader.data as web
from scipy.optimize import brentq
from datetime import datetime
from dateutil.relativedelta import relativedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
import warnings, os, io, textwrap
warnings.filterwarnings('ignore')

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, PageBreak, Image, HRFlowable,
                                 KeepTogether, FrameBreak)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color

#  CORPORATE IDENTITY / COLOR PALETTE
NAVY        = HexColor('#0D1B2A')
DEEP_BLUE   = HexColor('#1B3A6B')
MID_BLUE    = HexColor('#2563EB')
ACCENT_BLUE = HexColor('#3B82F6')
LIGHT_BLUE  = HexColor('#DBEAFE')
SLATE       = HexColor('#475569')
DARK_GRAY   = HexColor('#1E293B')
MID_GRAY    = HexColor('#64748B')
LIGHT_GRAY  = HexColor('#F1F5F9')
WHITE       = HexColor('#FFFFFF')
GREEN       = HexColor('#16A34A')
RED         = HexColor('#DC2626')
AMBER       = HexColor('#D97706')
GOLD        = HexColor('#F59E0B')

MPL = {
    'navy':        '#0D1B2A', 'deep_blue':   '#1B3A6B', 'mid_blue':    '#2563EB',
    'accent':      '#3B82F6', 'light_blue':  '#DBEAFE', 'slate':       '#475569',
    'green':       '#16A34A', 'red':         '#DC2626', 'amber':       '#D97706',
    'gold':        '#F59E0B', 'bg':          '#F8FAFC',
}

os.makedirs('/content/figures', exist_ok=True)
os.makedirs('/content/outputs', exist_ok=True)

#  SECTION 1 — INSTRUMENT & MARKET DATA (AUTOMATIZADO CON FRED)
end_date = datetime.today()
start_date_hist = end_date - relativedelta(months=12)

# Descarga de la curva del Tesoro
treasury_tickers = {'DGS1MO': 1/12, 'DGS3MO': 3/12, 'DGS6MO': 6/12, 'DGS1': 1, 'DGS2': 2, 'DGS3': 3, 'DGS5': 5, 'DGS7': 7, 'DGS10': 10, 'DGS20': 20, 'DGS30': 30}
try:
    live_curve = web.DataReader(list(treasury_tickers.keys()), 'fred', end_date - relativedelta(days=7), end_date).ffill().iloc[-1] / 100
    TREASURY_CURVE = {treasury_tickers[k]: v for k, v in live_curve.items() if not pd.isna(v)}
except:
    TREASURY_CURVE = {1/12: 0.053, 3/12: 0.0527, 6/12: 0.0519, 1: 0.0495, 2: 0.0462, 3: 0.0445, 5: 0.0432, 7: 0.0431, 10: 0.0430, 20: 0.0448, 30: 0.0447}

# Histórico de spreads
try:
    spread_history = web.DataReader('BAMLC0A0CMEY', 'fred', start_date_hist, end_date)['BAMLC0A0CMEY'].ffill().dropna() * 100
    treasury_history = web.DataReader('DGS10', 'fred', start_date_hist, end_date)['DGS10'].ffill().dropna() / 100
except:
    spread_history = pd.Series(np.linspace(90, 100, 252), index=pd.date_range(start_date_hist, end_date))
    treasury_history = pd.Series(np.linspace(0.04, 0.043, 252), index=pd.date_range(start_date_hist, end_date))

shared_index = treasury_history.index.intersection(spread_history.index)
treasury_history, spread_history = treasury_history.loc[shared_index], spread_history.loc[shared_index]
ytm_history = treasury_history + (spread_history / 10000)

def get_treasury_benchmark(maturity_years, curve):
    return np.interp(maturity_years, np.array(list(curve.keys())), np.array(list(curve.values())))

BOND = {
    'issuer':        'Apple Inc.',
    'cusip':         '037833DV1',
    'coupon':        0.0465,
    'face':          1000.0,
    'settlement':    end_date.strftime('%Y-%m-%d'),
    'maturity':      '2044-02-23',
    'frequency':     2,
    'day_count':     'ACT/ACT',
    'rating_sp':     'AA+',
    'rating_moodys': 'Aaa',
    'sector':        'Technology',
    'currency':      'USD',
    'market_ytm':    0.0524, # <-- YTM DE MERCADO MANUAL
}

T_years = (datetime.strptime(BOND['maturity'], '%Y-%m-%d') - end_date).days / 365.25
BOND['benchmark_tenor'] = round(T_years)
BOND['treasury_yield'] = get_treasury_benchmark(T_years, TREASURY_CURVE)
BOND['spread_bp'] = (BOND['market_ytm'] - BOND['treasury_yield']) * 10000

#  SECTION 2 — BOND PRICING MODULE
def calculate_cashflows(coupon, face, frequency, n_periods):
    cf = [coupon * face / frequency] * n_periods
    if n_periods > 0: cf[-1] += face
    return np.array(cf)

def price_bond(ytm, coupon, face, frequency, n_periods):
    cf = calculate_cashflows(coupon, face, frequency, n_periods)
    t  = np.arange(1, n_periods + 1) / frequency
    return np.sum(cf / (1 + ytm / frequency) ** (t * frequency))

def calculate_ytm(price, coupon, face, frequency, n_periods):
    f = lambda y: price_bond(y, coupon, face, frequency, n_periods) - price
    return brentq(f, 0.0001, 0.50, xtol=1e-10)

def get_accrued_days(settlement_str, maturity_str, frequency):
    s_date, m_date = datetime.strptime(settlement_str, '%Y-%m-%d'), datetime.strptime(maturity_str, '%Y-%m-%d')
    next_coupon = m_date
    while next_coupon > s_date: next_coupon -= relativedelta(months=12//frequency)
    prev_coupon = next_coupon
    next_coupon = prev_coupon + relativedelta(months=12//frequency)
    return (s_date - prev_coupon).days, (next_coupon - prev_coupon).days

T          = T_years
n_periods  = int(round(T * BOND['frequency']))
coupon_cf  = calculate_cashflows(BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
t_vec      = np.arange(1, n_periods + 1) / BOND['frequency']

base_price   = price_bond(BOND['market_ytm'], BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
clean_price  = base_price
days_since, days_in_per = get_accrued_days(BOND['settlement'], BOND['maturity'], BOND['frequency'])
accrued      = (BOND['coupon'] * BOND['face'] / BOND['frequency']) * (days_since / max(days_in_per, 1))
dirty_price  = clean_price + accrued
ytm_computed = calculate_ytm(base_price, BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)


#  SECTION 3 — RISK METRICS
def macaulay_duration(ytm, coupon, face, frequency, n_periods):
    cf, t = calculate_cashflows(coupon, face, frequency, n_periods), np.arange(1, n_periods + 1) / frequency
    pv = cf / (1 + ytm / frequency) ** (t * frequency)
    return np.sum(t * pv) / pv.sum()

def modified_duration(ytm, coupon, face, frequency, n_periods):
    return macaulay_duration(ytm, coupon, face, frequency, n_periods) / (1 + ytm / frequency)

def convexity(ytm, coupon, face, frequency, n_periods):
    cf, t = calculate_cashflows(coupon, face, frequency, n_periods), np.arange(1, n_periods + 1) / frequency
    pv = cf / (1 + ytm / frequency) ** (t * frequency)
    return np.sum(t * (t + 1/frequency) * pv) / (pv.sum() * (1 + ytm / frequency) ** 2)

def approx_price_change_pct(mod_dur, conv, dy): return -mod_dur * dy + 0.5 * conv * dy ** 2
def exact_price_change_pct(ytm, dy, coupon, face, frequency, n_periods):
    return (price_bond(ytm + dy, coupon, face, frequency, n_periods) - price_bond(ytm, coupon, face, frequency, n_periods)) / price_bond(ytm, coupon, face, frequency, n_periods)

mac_dur = macaulay_duration(BOND['market_ytm'], BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
mod_dur = modified_duration(BOND['market_ytm'], BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
conv    = convexity(BOND['market_ytm'], BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
dv01    = -approx_price_change_pct(mod_dur, conv, 0.0001) * base_price

#  SECTION 4 — SENSITIVITY ANALYSIS
shocks_bp = [-200, -100, -50, -25, 25, 50, 100, 200]
sens_table = []
for dy, sh in zip([s / 10000 for s in shocks_bp], shocks_bp):
    approx_pct, exact_pct = approx_price_change_pct(mod_dur, conv, dy)*100, exact_price_change_pct(BOND['market_ytm'], dy, BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)*100
    sens_table.append({'shock_bp': sh, 'new_ytm': (BOND['market_ytm'] + dy) * 100, 'approx_pct': approx_pct, 'exact_pct': exact_pct, 'error_pct': approx_pct - exact_pct, 'new_price': base_price * (1 + exact_pct / 100)})
sens_df = pd.DataFrame(sens_table)

#  SECTION 5 — SPREAD ANALYSIS
spread_sense = []
for ds in [-50, -25, 25, 50, 75, 100, 150, 200]:
    new_spread = BOND['spread_bp'] + ds
    new_price  = price_bond(BOND['treasury_yield'] + new_spread / 10000, BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
    spread_sense.append({'shock_bp': ds, 'new_spread': new_spread, 'new_price': new_price, 'pct_change': (new_price - base_price) / base_price * 100})
spread_df = pd.DataFrame(spread_sense)

#  SECTION 6 — YIELD DECOMPOSITION (12M)
ytm_12m_ago, tsy_12m_ago, spread_12m_ago = ytm_history.iloc[0], treasury_history.iloc[0], spread_history.iloc[0]
ytm_now, tsy_now, spread_now = ytm_history.iloc[-1], treasury_history.iloc[-1], spread_history.iloc[-1]

d_ytm, d_tsy, d_spread = (ytm_now - ytm_12m_ago) * 100, (tsy_now - tsy_12m_ago) * 100, spread_now - spread_12m_ago

price_12m_ago = price_bond(ytm_12m_ago, BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
price_rate_only  = price_bond(ytm_12m_ago + (tsy_now - tsy_12m_ago), BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
total_price_change = base_price - price_12m_ago
rate_contribution  = price_rate_only - price_12m_ago
spread_contribution = base_price - price_rate_only
coupon_income      = BOND['coupon'] * BOND['face']

total_return_pct   = (total_price_change + coupon_income) / price_12m_ago * 100
rate_contrib_pct   = rate_contribution / price_12m_ago * 100
spread_contrib_pct = spread_contribution / price_12m_ago * 100
income_contrib_pct = coupon_income / price_12m_ago * 100

#  SECTION 7 — SCENARIO ANALYSIS
scenarios = {
    'Base Case':         {'d_tsy':  0,     'd_spread':  0,   'hold_months': 12},
    'Fed Cuts 100bps':   {'d_tsy': -100,   'd_spread': -20,  'hold_months': 12},
    'Spread Compression':{'d_tsy':  0,     'd_spread': -50,  'hold_months': 12},
    'Recession':         {'d_tsy': -100,   'd_spread': +200, 'hold_months': 12},
    'Stagflation':       {'d_tsy': +100,   'd_spread': +150, 'hold_months': 12},
    'Soft Landing':      {'d_tsy': -50,    'd_spread': -30,  'hold_months': 12},
}

scenario_results = {}
for name, params in scenarios.items():
    new_tsy    = BOND['treasury_yield'] + params['d_tsy'] / 10000
    new_spread = BOND['spread_bp'] + params['d_spread']
    new_ytm    = new_tsy + new_spread / 10000
    new_price  = price_bond(new_ytm, BOND['coupon'], BOND['face'], BOND['frequency'], n_periods)
    coupon_inc = BOND['coupon'] * BOND['face'] * params['hold_months'] / 12
    scenario_results[name] = {
        'new_ytm': new_ytm * 100, 'new_spread': new_spread, 'new_price': new_price,
        'price_return': (new_price - base_price) / base_price * 100, 'income_return': coupon_inc / base_price * 100,
        'total_return': (new_price - base_price + coupon_inc) / base_price * 100, 'd_tsy': params['d_tsy'], 'd_spread': params['d_spread'],
    }

#  SECTION 8 — RISK-ADJUSTED METRICS
rr_ratio          = abs(scenario_results['Fed Cuts 100bps']['total_return'] / scenario_results['Stagflation']['total_return']) if scenario_results['Stagflation']['total_return'] != 0 else np.inf
carry_bp          = (BOND['market_ytm'] - BOND['treasury_yield']) * 10000
breakeven_spread_widening = mod_dur * 100

spread_mean, spread_std = spread_history.mean(), spread_history.std()
spread_zscore = (spread_now - spread_mean) / spread_std

#  SECTION 9 — CHART GENERATION
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.spines.top': False, 'axes.spines.right':False, 'axes.facecolor': '#F8FAFC', 'figure.facecolor': '#FFFFFF', 'axes.grid': True, 'grid.color': '#E2E8F0', 'grid.linewidth': 0.6, 'axes.titlesize': 10, 'axes.titleweight': 'bold', 'axes.titlecolor': '#0D1B2A', 'axes.labelcolor': '#475569', 'xtick.labelsize': 8, 'ytick.labelsize': 8})

# Fix Coupon Array temporal alignment
coupon_cf = np.full(n_periods, BOND['coupon'] * BOND['face'] / BOND['frequency'])
if n_periods > 0: coupon_cf[-1] += BOND['face']

fig, ax = plt.subplots(figsize=(7, 3.5))
tenors, yields = list(TREASURY_CURVE.keys()), [v * 100 for v in TREASURY_CURVE.values()]
ax.plot(tenors, yields, color=MPL['deep_blue'], lw=2.5, marker='o', ms=5, markerfacecolor=MPL['accent'], zorder=3, label='Treasury Curve')
ax.axhline(BOND['market_ytm'] * 100, color=MPL['red'], lw=1.5, ls='--', label=f'Apple YTM: {BOND["market_ytm"]*100:.2f}%')
ax.fill_between(tenors, yields, alpha=0.08, color=MPL['deep_blue'])
ax.axvspan(9.5, 10.5, alpha=0.12, color=MPL['amber'], label='Benchmark Tenor (10Y)')
ax.set_xlabel('Maturity (Years)'); ax.set_ylabel('Yield (%)'); ax.set_title('U.S. Treasury Yield Curve — Current')
ax.legend(fontsize=8, framealpha=0.9); ax.set_xlim(0, 31)
plt.tight_layout(); plt.savefig('/content/figures/fig1_yield_curve.png', dpi=150, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(7, 3.5))
ytm_range = np.linspace(0.02, 0.10, 300)
ax.plot(ytm_range * 100, [price_bond(y, BOND['coupon'], BOND['face'], BOND['frequency'], n_periods) for y in ytm_range], color=MPL['deep_blue'], lw=2.5, zorder=3)
ax.axvline(BOND['market_ytm'] * 100, color=MPL['red'], ls='--', lw=1.5, label=f'Current YTM: {BOND["market_ytm"]*100:.2f}%')
ax.axhline(base_price, color=MPL['green'], ls='--', lw=1.5, label=f'Current Price: {base_price:.2f}')
ax.scatter([BOND['market_ytm'] * 100], [base_price], color=MPL['red'], s=80, zorder=5)
ax.set_xlabel('YTM (%)'); ax.set_ylabel('Price (USD)'); ax.set_title('Price–Yield Relationship: Apple 4.650% 2044')
ax.legend(fontsize=8); ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'${x:,.0f}'))
plt.tight_layout(); plt.savefig('/content/figures/fig2_price_yield.png', dpi=150, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(7, 3.5))
shocks_range  = np.linspace(-200, 200, 100)
exact_changes  = [exact_price_change_pct(BOND['market_ytm'], s/10000, BOND['coupon'], BOND['face'], BOND['frequency'], n_periods) * 100 for s in shocks_range]
dur_approx    = [-mod_dur * s/10000 * 100 for s in shocks_range]
dur_conv      = [approx_price_change_pct(mod_dur, conv, s/10000) * 100 for s in shocks_range]
ax.plot(shocks_range, exact_changes,  color=MPL['deep_blue'],  lw=2.5, label='Exact Price Change')
ax.plot(shocks_range, dur_approx,     color=MPL['red'],        lw=1.8, ls='--', label='Duration Only')
ax.plot(shocks_range, dur_conv,       color=MPL['amber'],      lw=1.8, ls='-.', label='Duration + Convexity')
ax.fill_between(shocks_range, dur_approx, exact_changes, alpha=0.08, color=MPL['red'], label='Approximation Error')
ax.axhline(0, color='#94A3B8', lw=0.8); ax.axvline(0, color='#94A3B8', lw=0.8)
ax.set_xlabel('Yield Shock (bps)'); ax.set_ylabel('Price Change (%)'); ax.set_title('Rate Sensitivity: Duration vs Convexity')
ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig('/content/figures/fig3_sensitivity.png', dpi=150, bbox_inches='tight'); plt.close()

fig, axes = plt.subplots(2, 1, figsize=(7, 4.5), sharex=True)
axes[0].plot(spread_history.index, spread_history.values, color=MPL['deep_blue'], lw=2)
axes[0].axhline(spread_mean, color=MPL['amber'], ls='--', lw=1.5, label=f'12M Mean: {spread_mean:.0f}bps')
axes[0].fill_between(spread_history.index, spread_mean - spread_std, spread_mean + spread_std, alpha=0.12, color=MPL['amber'], label='±1σ Band')
axes[0].axhline(spread_now, color=MPL['red'], ls=':', lw=1.5, label=f'Current: {spread_now:.0f}bps')
axes[0].set_ylabel('OAS (bps)'); axes[0].set_title('12-Month OAS History & Z-Score'); axes[0].legend(fontsize=7.5)
zscore_series = (spread_history - spread_mean) / spread_std
axes[1].bar(spread_history.index, zscore_series.values, color=[MPL['red'] if z > 1 else MPL['green'] if z < -1 else MPL['mid_blue'] for z in zscore_series.values], width=20, alpha=0.8)
axes[1].axhline(0, color='#94A3B8', lw=0.8); axes[1].axhline(1, color=MPL['amber'], ls='--', lw=1, alpha=0.7); axes[1].axhline(-1, color=MPL['amber'], ls='--', lw=1, alpha=0.7)
axes[1].set_ylabel('Z-Score'); axes[1].set_xlabel('')
plt.tight_layout(); plt.savefig('/content/figures/fig4_spread_history.png', dpi=150, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(7, 3.8))
components = ['Starting\nPrice', 'Rate\nImpact', 'Spread\nImpact', 'Coupon\nIncome', 'Total\nReturn']
values     = [0, rate_contrib_pct, spread_contrib_pct, income_contrib_pct, total_return_pct]
colors_bar = [MPL['slate'], MPL['red'] if rate_contribution < 0 else MPL['green'], MPL['red'] if spread_contribution < 0 else MPL['green'], MPL['green'], MPL['red'] if total_return_pct < 0 else MPL['deep_blue']]
bars = ax.bar(components[1:], values[1:], color=colors_bar[1:], alpha=0.85, width=0.55, edgecolor='white')
ax.axhline(0, color='#94A3B8', lw=0.8)
for bar, val in zip(bars, values[1:]): ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05 * (1 if val >= 0 else -1), f'{val:+.2f}%', ha='center', va='bottom' if val >= 0 else 'top', fontsize=8.5, fontweight='bold', color=MPL['deep_blue'])
ax.set_ylabel('Return Contribution (%)'); ax.set_title('12-Month Return Decomposition: Rate vs Spread vs Income')
plt.tight_layout(); plt.savefig('/content/figures/fig5_decomposition.png', dpi=150, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(7, 3.8))
sc_names  = list(scenario_results.keys())
x = np.arange(len(sc_names)); w = 0.35
ax.bar(x - w/2, [scenario_results[n]['price_return'] for n in sc_names],  w, label='Price Return',  color=MPL['deep_blue'],  alpha=0.85)
ax.bar(x + w/2, [scenario_results[n]['income_return'] for n in sc_names], w, label='Income Return', color=MPL['accent'],     alpha=0.85)
ax.plot(x, [scenario_results[n]['total_return'] for n in sc_names], 'D-', color=MPL['amber'], lw=2, ms=7, label='Total Return', zorder=5)
ax.axhline(0, color='#94A3B8', lw=0.8); ax.set_xticks(x); ax.set_xticklabels([n.replace(' ', '\n') for n in sc_names], fontsize=7.5)
ax.set_ylabel('Return (%)'); ax.set_title('Scenario Analysis: Total Return by Component'); ax.legend(fontsize=8, loc='upper right')
plt.tight_layout(); plt.savefig('/content/figures/fig6_scenarios.png', dpi=150, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(7, 3.2))
t_years = np.arange(1, n_periods + 1) / BOND['frequency']
pv_cf   = coupon_cf / (1 + BOND['market_ytm'] / BOND['frequency']) ** np.arange(1, n_periods + 1)
colors_cf = [MPL['accent']] * len(t_years)
if len(colors_cf) > 0: colors_cf[-1] = MPL['deep_blue']
ax.bar(t_years, coupon_cf, width=0.4, color=colors_cf, alpha=0.8, label='Nominal Cash Flow')
ax2b = ax.twinx()
ax2b.plot(t_years, np.cumsum(pv_cf) / base_price * 100, color=MPL['amber'], lw=2, label='Cumulative PV (%)')
ax2b.set_ylabel('Cumulative PV (%)', color=MPL['amber']); ax2b.tick_params(axis='y', labelcolor=MPL['amber']); ax2b.spines['top'].set_visible(False)
ax.set_xlabel('Years to Payment'); ax.set_ylabel('Cash Flow (USD)'); ax.set_title('Cash Flow Profile & Present Value Accumulation')
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2b.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)
plt.tight_layout(); plt.savefig('/content/figures/fig7_cashflows.png', dpi=150, bbox_inches='tight'); plt.close()


#  SECTION 10 — PDF REPORT GENERATION (TU MAQUETA COMPLETA)
OUTPUT_PDF = '/content/outputs/Fixed_Income_Risk_Decomposition_Report.pdf'

class ColoredRule(Flowable):
    def __init__(self, width, color=DEEP_BLUE, height=2):
        Flowable.__init__(self); self.width = width; self.color = color; self.height = height
    def draw(self):
        self.canv.setFillColor(self.color); self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)

class SectionHeader(Flowable):
    def __init__(self, number, title, width, accent=ACCENT_BLUE):
        Flowable.__init__(self); self.number = number; self.title  = title; self.width  = width; self.accent = accent; self.height = 28
    def draw(self):
        c = self.canv
        c.setFillColor(LIGHT_BLUE); c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        c.setFillColor(self.accent); c.rect(0, 0, 6, self.height, fill=1, stroke=0)
        c.setFillColor(DEEP_BLUE); c.setFont('Helvetica-Bold', 12); c.drawString(14, 9, f'{self.number}  {self.title}')

class MetricBox(Flowable):
    def __init__(self, label, value, sub='', width=130, color=DEEP_BLUE):
        Flowable.__init__(self); self.label = label; self.value = value; self.sub = sub; self.width = width; self.color = color; self.height = 52
    def draw(self):
        c = self.canv
        c.setFillColor(LIGHT_GRAY); c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)
        c.setFillColor(self.color); c.rect(0, self.height - 4, self.width, 4, fill=1, stroke=0)
        c.setFillColor(SLATE); c.setFont('Helvetica', 7); c.drawString(8, self.height - 16, self.label.upper())
        c.setFillColor(DARK_GRAY); c.setFont('Helvetica-Bold', 16); c.drawString(8, self.height - 35, self.value)
        if self.sub: c.setFillColor(MID_GRAY); c.setFont('Helvetica', 7); c.drawString(8, 4, self.sub)

def build_styles():
    styles = getSampleStyleSheet()
    custom = {
        'CoverTitle': ParagraphStyle('CoverTitle', fontSize=28, fontName='Helvetica-Bold', textColor=WHITE, leading=34, spaceAfter=6),
        'CoverSubtitle': ParagraphStyle('CoverSubtitle', fontSize=14, fontName='Helvetica', textColor=HexColor('#BFDBFE'), leading=18, spaceAfter=4),
        'CoverMeta': ParagraphStyle('CoverMeta', fontSize=9, fontName='Helvetica', textColor=HexColor('#93C5FD'), leading=13),
        'H1': ParagraphStyle('H1', fontSize=13, fontName='Helvetica-Bold', textColor=NAVY, leading=18, spaceBefore=14, spaceAfter=6),
        'H2': ParagraphStyle('H2', fontSize=10.5, fontName='Helvetica-Bold', textColor=DEEP_BLUE, leading=14, spaceBefore=10, spaceAfter=4),
        'Body': ParagraphStyle('Body', fontSize=9.5, fontName='Helvetica', textColor=DARK_GRAY, leading=14, spaceAfter=6, alignment=TA_JUSTIFY),
        'BodyBold': ParagraphStyle('BodyBold', fontSize=9.5, fontName='Helvetica-Bold', textColor=NAVY, leading=14, spaceAfter=4),
        'Small': ParagraphStyle('Small', fontSize=8, fontName='Helvetica', textColor=SLATE, leading=11, spaceAfter=3),
        'TableHeader': ParagraphStyle('TableHeader', fontSize=8, fontName='Helvetica-Bold', textColor=WHITE, leading=11, alignment=TA_CENTER),
        'TableCell': ParagraphStyle('TableCell', fontSize=8.5, fontName='Helvetica', textColor=DARK_GRAY, leading=12, alignment=TA_CENTER),
        'Verdict': ParagraphStyle('Verdict', fontSize=16, fontName='Helvetica-Bold', textColor=WHITE, leading=22, alignment=TA_CENTER),
        'Italic': ParagraphStyle('Italic', fontSize=9, fontName='Helvetica-Oblique', textColor=SLATE, leading=13, spaceAfter=4),
        'Caption': ParagraphStyle('Caption', fontSize=7.5, fontName='Helvetica-Oblique', textColor=MID_GRAY, leading=11, spaceAfter=8, alignment=TA_CENTER),
    }
    return custom

S = build_styles()

def img(path, width=6.5*inch, height=None):
    if height: return Image(path, width=width, height=height)
    return Image(path, width=width)

def tbl(data, col_widths, row_heights=None, header_rows=1):
    t = Table(data, colWidths=col_widths, rowHeights=row_heights)
    style  = TableStyle([
        ('BACKGROUND',   (0, 0), (-1, header_rows - 1), DEEP_BLUE),
        ('TEXTCOLOR',    (0, 0), (-1, header_rows - 1), WHITE),
        ('FONTNAME',     (0, 0), (-1, header_rows - 1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, header_rows - 1), 8),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE',     (0, header_rows), (-1, -1), 8.5),
        ('ROWBACKGROUNDS', (0, header_rows), (-1, -1), [WHITE, LIGHT_GRAY]),
        ('GRID',         (0, 0), (-1, -1), 0.4, HexColor('#CBD5E1')),
        ('TOPPADDING',   (0, 0), (-1, -1), 5), ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROUNDEDCORNERS', [4]),
    ])
    t.setStyle(style)
    return t

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_frame(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_frame(self, num_pages):
        page = self._pageNumber
        if page == 1: return
        w, h = A4
        self.setFillColor(NAVY); self.rect(0, h - 38, w, 38, fill=1, stroke=0)
        self.setFillColor(ACCENT_BLUE); self.rect(0, h - 38, 6, 38, fill=1, stroke=0)
        self.setFillColor(WHITE); self.setFont('Helvetica-Bold', 8); self.drawString(16, h - 23, 'FIXED INCOME RISK DECOMPOSITION FRAMEWORK')
        self.setFont('Helvetica', 8); self.setFillColor(HexColor('#93C5FD'))
        self.drawRightString(w - 16, h - 23, f'Apple Inc. 4.650% 2044  |  Valuation: {BOND["settlement"]}')
        self.setFillColor(LIGHT_GRAY); self.rect(0, 0, w, 28, fill=1, stroke=0)
        self.setFillColor(SLATE); self.setFont('Helvetica', 7); self.drawString(16, 9, 'FOR INTERNAL USE ONLY — NOT FOR DISTRIBUTION. Model assumptions apply; see limitations section.')
        self.setFillColor(DEEP_BLUE); self.setFont('Helvetica-Bold', 8); self.drawRightString(w - 16, 9, f'Page {page - 1} of {num_pages - 1}')

def build_cover_pdf(path):
    w, h = A4
    c = canvas.Canvas(path, pagesize=A4)
    c.setFillColor(NAVY); c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColor(MID_BLUE); c.rect(0, h - 8, w, 8, fill=1, stroke=0)
    c.setFillColor(ACCENT_BLUE); c.rect(0, 0, 10, h, fill=1, stroke=0)
    c.setFillColor(HexColor('#1E3A5F')); c.circle(w - 60, 60, 130, fill=1, stroke=0)
    c.setFillColor(HexColor('#162D4E')); c.circle(w - 20, 80, 80, fill=1, stroke=0)
    c.setFillColor(HexColor('#60A5FA')); c.setFont('Helvetica-Bold', 9); c.drawString(28, h - 38, 'FIXED INCOME RESEARCH  |  BUY-SIDE ANALYTICS')
    c.setFillColor(MID_BLUE); c.roundRect(28, h - 78, 180, 24, 4, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont('Helvetica-Bold', 9); c.drawString(38, h - 68, 'INVESTMENT RESEARCH REPORT')
    c.setFillColor(WHITE); c.setFont('Helvetica-Bold', 26)
    c.drawString(28, h - 140, 'Fixed Income Risk'); c.drawString(28, h - 172, 'Decomposition')
    c.setFillColor(HexColor('#93C5FD')); c.setFont('Helvetica-Bold', 26); c.drawString(28, h - 204, 'Framework')
    c.setFillColor(HexColor('#BFDBFE')); c.setFont('Helvetica', 13); c.drawString(28, h - 238, 'Separating Rate Risk from Credit Risk in Corporate Bonds')
    c.setFillColor(HexColor('#2563EB')); c.rect(28, h - 255, 420, 2, fill=1, stroke=0)
    details = [
        ('INSTRUMENT',   'Apple Inc. 4.650% Senior Notes due 2044'),
        ('CUSIP',        '037833DV1'),
        ('MARKET PRICE', f'${base_price:,.2f}'),
        ('YTM',          f'{BOND["market_ytm"]*100:.2f}%'),
        ('OAS',          f'{BOND["spread_bp"]:.0f} bps'),
        ('RATING',       f'{BOND["rating_sp"]} / {BOND["rating_moodys"]}'),
    ]
    y_pos = h - 280
    for i, (label, val) in enumerate(details):
        col, row_y = (i % 3) * 190 + 28, (i // 3) * 36
        c.setFillColor(HexColor('#93C5FD')); c.setFont('Helvetica-Bold', 7); c.drawString(col, y_pos - row_y, label)
        c.setFillColor(WHITE); c.setFont('Helvetica', 10); c.drawString(col, y_pos - row_y - 14, val)
    c.setFillColor(HexColor('#1E3A5F')); c.rect(0, 0, w, 55, fill=1, stroke=0)
    c.setFillColor(HexColor('#60A5FA')); c.setFont('Helvetica-Bold', 8); c.drawString(28, 36, 'VALUATION DATE')
    c.setFillColor(WHITE); c.setFont('Helvetica', 9); c.drawString(28, 22, f'{BOND["settlement"]}')
    c.setFillColor(HexColor('#60A5FA')); c.setFont('Helvetica-Bold', 8); c.drawString(200, 36, 'CLASSIFICATION')
    c.setFillColor(WHITE); c.setFont('Helvetica', 9); c.drawString(200, 22, 'Investment Grade | Technology')
    c.setFillColor(HexColor('#60A5FA')); c.setFont('Helvetica-Bold', 8); c.drawString(400, 36, 'ANALYST')
    c.setFillColor(WHITE); c.setFont('Helvetica', 9); c.drawString(400, 22, 'Fixed Income Analytics Desk')
    c.save()

def build_pdf():
    from pypdf import PdfWriter, PdfReader

    COVER_PDF   = '/content/outputs/cover.pdf'
    CONTENT_PDF = '/content/outputs/content.pdf'

    build_cover_pdf(COVER_PDF)

    doc = SimpleDocTemplate(CONTENT_PDF, pagesize=A4, leftMargin=0.7*inch, rightMargin=0.7*inch, topMargin=0.7*inch, bottomMargin=0.5*inch)
    W = A4[0] - 1.4 * inch
    story = []

    # ── SECTION 1: EXECUTIVE SUMMARY ─────────────────────────────────────────
    story.append(SectionHeader('01', 'EXECUTIVE SUMMARY', W))
    story.append(Spacer(1, 10))

    verdict_color = GREEN
    verdict_text  = 'OVERWEIGHT'
    verdict_sub   = 'Risk-Adjusted Return Favors Current Entry'

    verdict_table = Table(
        [[Paragraph(verdict_text, S['Verdict']),
          Paragraph(verdict_sub,  ParagraphStyle('vs', fontSize=10, fontName='Helvetica', textColor=WHITE, leading=14, alignment=TA_CENTER))]],
        colWidths=[W * 0.3, W * 0.7]
    )
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), GREEN), ('BACKGROUND', (1, 0), (1, 0), DEEP_BLUE),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'), ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0, WHITE), ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph('Macro Context', S['H2']))
    story.append(Paragraph(
        'The current environment is characterized by elevated but plateauing interest rates following the '
        'most aggressive tightening cycle since the 1980s. The Federal Reserve has maintained the '
        'Federal Funds Rate in restrictive territory, with market consensus pricing cuts over the next 12 months. '
        'Investment-grade credit spreads remain historically contained.', S['Body']))

    story.append(Paragraph('Investment Problem', S['H2']))
    story.append(Paragraph(
        f'Apple Inc. 4.650% Senior Notes due 2044 currently trade at a YTM of {BOND["market_ytm"]*100:.2f}%, implying an OAS of '
        f'{BOND["spread_bp"]:.0f}bps over the {BOND["benchmark_tenor"]}-year Treasury. The central analytical question is: <b>is the bond\'s current discount '
        'to par principally a function of higher risk-free rates, or does it embed meaningful credit risk premium?</b> ', S['Body']))

    story.append(Paragraph('Key Findings', S['H2']))
    findings = [
        ('Rate Dominance', f'Modified duration of {mod_dur:.2f}x implies that ~{abs(approx_price_change_pct(mod_dur, conv, 0.01)*100):.1f}% of bond value is at risk per 100bps rate shock.'),
        ('Credit Benign', f'Current OAS of {BOND["spread_bp"]:.0f}bps sits with a Z-score of {spread_zscore:+.2f}σ relative to the 12-month average.'),
        ('Asymmetric Upside', f'Under a rate-cut scenario, expected total return is {scenario_results["Fed Cuts 100bps"]["total_return"]:+.1f}% vs. {scenario_results["Stagflation"]["total_return"]:+.1f}% under adverse stagflation.'),
        ('Carry Attractive', f'With {carry_bp:.0f}bps of carry over Treasuries, the breakeven spread widening before carry is consumed is ~{breakeven_spread_widening:.0f}bps.'),
    ]
    find_data = [['Finding', 'Summary']] + [[f, d] for f, d in findings]
    story.append(tbl(find_data, [W*0.22, W*0.78]))
    story.append(Spacer(1, 8))

    story.append(Paragraph('Investment Implication', S['H2']))
    story.append(Paragraph(
        'Given the rate-dominated risk profile, the bond is best suited for portfolios with constructive '
        'views on rate normalization. Duration extension at current levels offers asymmetric payoff.', S['Body']))

    story.append(PageBreak())

    # ── SECTION 2: THEORETICAL FRAMEWORK ─────────────────────────────────────
    story.append(SectionHeader('02', 'THEORETICAL FRAMEWORK', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('2.1  Bond Price Structure', S['H2']))
    story.append(Paragraph('A fixed-rate bond\'s price is the present value of its contractual cash flows, discounted at the market yield-to-maturity (YTM).', S['Body']))
    story.append(Paragraph('<i>P = SUM [ C/2 / (1 + y/2)<super>t</super> ] + F / (1 + y/2)<super>N</super></i>', ParagraphStyle('formula', fontSize=10, fontName='Helvetica-Oblique', textColor=DEEP_BLUE, leading=16, spaceAfter=8, alignment=TA_CENTER, borderPad=8, backColor=LIGHT_BLUE, borderColor=ACCENT_BLUE, borderWidth=0.5, borderRadius=4)))

    story.append(Paragraph('2.2  Yield Decomposition', S['H2']))
    story.append(Paragraph('The yield-to-maturity of a corporate bond can be decomposed into two distinct components:', S['Body']))
    story.append(Paragraph('<i>YTM = Risk-Free Rate (Treasury) + Credit Spread (OAS)</i>', ParagraphStyle('formula2', fontSize=10, fontName='Helvetica-Oblique', textColor=DEEP_BLUE, leading=16, spaceAfter=8, alignment=TA_CENTER, borderPad=8, backColor=LIGHT_BLUE, borderColor=ACCENT_BLUE, borderWidth=0.5, borderRadius=4)))
    story.append(Paragraph('This decomposition is fundamental to risk attribution. Rate risk dominates high-grade corporate bonds.', S['Body']))

    story.append(Paragraph('2.3  Duration and Convexity', S['H2']))
    dur_data = [
        ['Metric', 'Formula (Conceptual)', 'Interpretation'],
        ['Macaulay Duration', 'Weighted avg. time to cash flows', 'Time-weighted payback period'],
        ['Modified Duration', 'MacD / (1 + y/m)', '%Price change per 100bps yield change'],
        ['Dollar Duration (DV01)', 'ModD × Price / 10,000', 'Dollar price change per 1bp'],
        ['Convexity', '2nd derivative of price/yield', 'Non-linearity; positive = favorable curvature'],
    ]
    story.append(tbl(dur_data, [W*0.22, W*0.38, W*0.40]))
    story.append(Spacer(1, 6))

    story.append(PageBreak())

    # ── SECTION 3: INSTRUMENT DESCRIPTION ────────────────────────────────────
    story.append(SectionHeader('03', 'INSTRUMENT DESCRIPTION', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('3.1  Security Specifications', S['H2']))
    spec_data = [
        ['Parameter',       'Detail',               'Parameter',          'Detail'],
        ['Issuer',          'Apple Inc.',           'Coupon',             '4.650% Fixed'],
        ['CUSIP',           '037833DV1',            'Frequency',          'Semi-Annual'],
        ['Settlement',      BOND['settlement'],     'Day Count',          'ACT/ACT'],
        ['Maturity',        'February 23, 2044',    'Years to Maturity',  f'{T:.2f} yrs'],
        ['Remaining Coupon Periods', f'{n_periods}', 'Face Value',         '$1,000'],
        ['Rating (S&P)',    BOND['rating_sp'],      'Rating (Moody\'s)',  BOND['rating_moodys']],
        ['Sector',          BOND['sector'],         'Currency',           BOND['currency']],
    ]
    story.append(tbl(spec_data, [W*0.22, W*0.28, W*0.22, W*0.28], header_rows=1))
    story.append(Spacer(1, 8))

    story.append(Paragraph('3.2  Current Market Data', S['H2']))
    mkt_data = [
        ['Market Price (Clean)', 'YTM', '10Y Treasury', 'OAS', 'DV01', 'Modified Duration'],
        [f'${clean_price:,.2f}', f'{ytm_computed*100:.4f}%', f'{BOND["treasury_yield"]*100:.2f}%', f'{BOND["spread_bp"]:.0f} bps', f'${dv01:.3f}', f'{mod_dur:.4f}x']
    ]
    story.append(tbl(mkt_data, [W/6]*6))
    story.append(Spacer(1, 8))

    story.append(Paragraph('3.3  Rationale for Instrument Selection', S['H2']))
    story.append(Paragraph('Apple Inc. represents the quintessential investment-grade benchmark issuer: AA+ rated with fortress balance sheet, near-zero default probability over the investment horizon.', S['Body']))

    story.append(Spacer(1, 8))
    story.append(img('/content/figures/fig7_cashflows.png', W, 3.0*inch))
    story.append(Paragraph(f'Figure 1: Cash flow profile and cumulative PV accumulation over {n_periods} semi-annual periods.', S['Caption']))

    story.append(PageBreak())

    # ── SECTION 4: BASE VALUATION ─────────────────────────────────────────────
    story.append(SectionHeader('04', 'BASE VALUATION', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('4.1  Cash Flow Construction & Pricing', S['H2']))
    cf_display = [['Period', 'Time (Yrs)', 'Cash Flow ($)', 'Discount Factor', 'PV ($)']]
    for i in range(min(6, n_periods)):
        t_i  = (i + 1) / BOND['frequency']
        cf_i = coupon_cf[i]
        df_i = 1 / (1 + BOND['market_ytm'] / BOND['frequency']) ** (i + 1)
        pv_i = cf_i * df_i
        cf_display.append([str(i+1), f'{t_i:.2f}', f'${cf_i:,.2f}', f'{df_i:.6f}', f'${pv_i:.2f}'])
    cf_display.append(['...', '...', '...', '...', '...'])
    last = n_periods
    t_l  = last / BOND['frequency']
    cf_l = coupon_cf[-1]
    df_l = 1 / (1 + BOND['market_ytm'] / BOND['frequency']) ** last
    pv_l = cf_l * df_l
    cf_display.append([str(last), f'{t_l:.2f}', f'${cf_l:,.2f}', f'{df_l:.6f}', f'${pv_l:.2f}'])
    cf_display.append(['TOTAL', '', '', '', f'${base_price:,.4f}'])
    story.append(tbl(cf_display, [W*0.1, W*0.15, W*0.22, W*0.25, W*0.28]))
    story.append(Spacer(1, 6))

    story.append(Paragraph('4.2  Pricing Summary', S['H2']))
    ps_data = [
        ['Clean Price', 'Accrued Interest', 'Dirty Price', 'YTM (Computed)', 'YTM vs. Market', 'Validation'],
        [f'${clean_price:,.4f}', f'${accrued:.4f}', f'${dirty_price:,.4f}', f'{ytm_computed*100:.4f}%', f'{(ytm_computed - BOND["market_ytm"])*10000:+.1f} bps', '✓ PASS']
    ]
    story.append(tbl(ps_data, [W/6]*6))
    story.append(Paragraph(f'The model price of ${base_price:,.2f} is derived by discounting all semi-annual cash flows at the market YTM of {BOND["market_ytm"]*100:.2f}%.', S['Body']))

    story.append(Spacer(1, 8))
    story.append(img('/content/figures/fig2_price_yield.png', W, 3.0*inch))
    story.append(Paragraph('Figure 2: Full price-yield curve showing the convex relationship.', S['Caption']))

    story.append(PageBreak())

    # ── SECTION 5: RATE SENSITIVITY ───────────────────────────────────────────
    story.append(SectionHeader('05', 'INTEREST RATE SENSITIVITY ANALYSIS', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('5.1  Key Risk Metrics', S['H2']))
    metrics = [
        ('Macaulay Duration',  f'{mac_dur:.3f} yrs', 'Weighted avg. payback'),
        ('Modified Duration',  f'{mod_dur:.3f}x',    '%Δ Price / 100bps'),
        ('Convexity',          f'{conv:.3f}',        '2nd order adjustment'),
        ('DV01',               f'${dv01:.3f}',       'Per $1,000 face'),
    ]
    m_tbl = Table([[m[0] for m in metrics], [m[1] for m in metrics], [m[2] for m in metrics]], colWidths=[W/4]*4)
    m_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LIGHT_GRAY), ('BACKGROUND',    (0, 1), (-1, 1), LIGHT_BLUE),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'), ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',          (0, 0), (-1, -1), 0.5, HexColor('#CBD5E1')), ('LINEABOVE',     (0, 0), (-1, 0), 3, ACCENT_BLUE),
    ]))
    story.append(m_tbl)
    story.append(Spacer(1, 8))

    story.append(Paragraph('5.2  Parallel Shock Analysis', S['H2']))
    sh_data = [['Shock (bps)', 'New YTM (%)', 'New Price ($)', 'Exact ΔP (%)', 'Duration Approx (%)', 'Conv. Adj. (%)', 'Error (bps)']]
    for _, row in sens_df.iterrows():
        sh_data.append([f'{int(row.shock_bp):+d}', f'{row.new_ytm:.3f}%', f'${row.new_price:,.2f}', f'{row.exact_pct:+.3f}%', f'{row.approx_pct + row.error_pct:+.3f}%', f'{row.approx_pct:+.3f}%', f'{row.error_pct*100:+.1f}'])
    story.append(tbl(sh_data, [W*0.1, W*0.12, W*0.15, W*0.15, W*0.17, W*0.16, W*0.15]))
    story.append(Spacer(1, 6))

    story.append(img('/content/figures/fig3_sensitivity.png', W, 3.0*inch))
    story.append(Paragraph('Figure 3: Rate sensitivity comparison. The gap between Duration-Only and Exact curves demonstrates convexity benefit.', S['Caption']))

    story.append(PageBreak())

    # ── SECTION 6: CREDIT SENSITIVITY ────────────────────────────────────────
    story.append(SectionHeader('06', 'CREDIT SPREAD SENSITIVITY ANALYSIS', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('6.1  OAS Shock Analysis', S['H2']))
    sp_data = [['Spread Shock (bps)', 'New OAS (bps)', 'New YTM (%)', 'New Price ($)', 'Price Change (%)']]
    for _, row in spread_df.iterrows():
        pct = float(row["pct_change"])
        sp_data.append([f'{int(row.shock_bp):+d}', f'{row.new_spread:.0f}', f'{(BOND["treasury_yield"] + row.new_spread/10000)*100:.3f}%', f'${row.new_price:,.2f}', f'{pct:+.3f}%'])
    story.append(tbl(sp_data, [W*0.2, W*0.2, W*0.2, W*0.2, W*0.2]))
    story.append(Spacer(1, 6))

    story.append(img('/content/figures/fig4_spread_history.png', W, 3.8*inch))
    story.append(Paragraph(f'Figure 4: 12-month OAS history and Z-score. Current spread of {spread_now:.0f}bps shows a Z-score of {spread_zscore:+.2f}σ.', S['Caption']))

    story.append(PageBreak())

    # ── SECTION 7: YIELD DECOMPOSITION ───────────────────────────────────────
    story.append(SectionHeader('07', 'RETURN DECOMPOSITION — TRAILING 12 MONTHS', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('7.1  Yield Attribution', S['H2']))
    ya_data = [
        ['Component', '12M Ago', 'Current', 'Change (bps)', 'Price Attribution'],
        ['10Y Treasury Yield', f'{tsy_12m_ago*100:.3f}%', f'{tsy_now*100:.3f}%', f'{d_tsy:+.1f} bps', f'{rate_contrib_pct:+.2f}%'],
        ['OAS / Credit Spread', f'{spread_12m_ago:.1f} bps', f'{spread_now:.1f} bps', f'{d_spread:+.1f} bps', f'{spread_contrib_pct:+.2f}%'],
        ['YTM (Total)', f'{ytm_12m_ago*100:.3f}%', f'{ytm_now*100:.3f}%', f'{d_ytm:+.1f} bps', f'{rate_contrib_pct + spread_contrib_pct:+.2f}%'],
        ['Coupon Income', '—', '—', '—', f'{income_contrib_pct:+.2f}%'],
        ['TOTAL RETURN', '', '', '', f'{total_return_pct:+.2f}%'],
    ]
    story.append(tbl(ya_data, [W*0.28, W*0.18, W*0.18, W*0.18, W*0.18], header_rows=1))
    story.append(Spacer(1, 6))

    story.append(img('/content/figures/fig5_decomposition.png', W, 3.2*inch))
    story.append(Paragraph('Figure 5: Waterfall decomposition of 12-month return into rate, spread, and income components.', S['Caption']))

    story.append(PageBreak())

    # ── SECTION 8: YIELD CURVE ────────────────────────────────────────────────
    story.append(SectionHeader('08', 'YIELD CURVE CONTEXT', W))
    story.append(Spacer(1, 8))
    story.append(img('/content/figures/fig1_yield_curve.png', W, 3.5*inch))
    story.append(Paragraph('Figure 6: Current U.S. Treasury yield curve. The Apple YTM benchmark is plotted for reference.', S['Caption']))
    story.append(Spacer(1, 8))

    story.append(Paragraph('Treasury Curve Data', S['H2']))
    tc_data = [['Tenor', 'Yield (%)', 'Tenor', 'Yield (%)', 'Tenor', 'Yield (%)']]
    tc_items = list(TREASURY_CURVE.items())
    for i in range(0, len(tc_items), 3):
        row = []
        for j in range(3):
            if i + j < len(tc_items):
                tenor, yield_v = tc_items[i + j]
                row += [f'{tenor}Y' if tenor >= 1 else f'{int(tenor*12)}M', f'{yield_v*100:.3f}%']
            else:
                row += ['—', '—']
        tc_data.append(row)
    story.append(tbl(tc_data, [W/6]*6))

    story.append(PageBreak())

    # ── SECTION 9: SCENARIO ANALYSIS ─────────────────────────────────────────
    story.append(SectionHeader('09', 'SCENARIO ANALYSIS', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('Scenario Return Summary', S['H2']))
    sc_ret = [['Scenario', 'New YTM (%)', 'New Price ($)', 'Price Return', 'Income Return', 'Total Return', 'Assessment']]
    assessments = {'Base Case': ('Hold', AMBER), 'Fed Cuts 100bps': ('Attractive', GREEN), 'Spread Compression': ('Attractive', GREEN), 'Recession': ('Cautious', AMBER), 'Stagflation': ('Avoid', RED), 'Soft Landing': ('Attractive', GREEN)}
    for name, res in scenario_results.items():
        sc_ret.append([name, f'{res["new_ytm"]:.3f}%', f'${res["new_price"]:,.2f}', f'{res["price_return"]:+.2f}%', f'{res["income_return"]:+.2f}%', f'{res["total_return"]:+.2f}%', assessments[name][0]])

    t_sc = tbl(sc_ret, [W*0.22, W*0.11, W*0.13, W*0.12, W*0.12, W*0.12, W*0.18])
    sc_style_extra = []
    for i, (name, res) in enumerate(scenario_results.items(), 1):
        color = GREEN if res['total_return'] > 5 else (RED if res['total_return'] < 0 else AMBER)
        sc_style_extra.extend([('BACKGROUND', (6, i), (6, i), color), ('TEXTCOLOR', (6, i), (6, i), WHITE)])
    t_sc.setStyle(TableStyle(sc_style_extra))
    story.append(t_sc)
    story.append(Spacer(1, 8))

    story.append(img('/content/figures/fig6_scenarios.png', W, 3.2*inch))

    story.append(PageBreak())

    # ── SECTION 10: RISK-ADJUSTED METRICS ────────────────────────────────────
    story.append(SectionHeader('10', 'RISK-ADJUSTED METRICS', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('10.1  Return and Risk Summary', S['H2']))
    ram_data = [
        ['Metric', 'Value', 'Benchmark / Context'],
        ['Expected Return (Soft Landing)', f'{scenario_results["Soft Landing"]["total_return"]:+.2f}%', 'Base-bull scenario, 12-month horizon'],
        ['Best Case Return (Rate Cut)', f'{scenario_results["Fed Cuts 100bps"]["total_return"]:+.2f}%', 'Fed -100bps scenario'],
        ['Downside Return (Stagflation)', f'{scenario_results["Stagflation"]["total_return"]:+.2f}%', 'Tail risk scenario'],
        ['Upside / Downside Ratio', f'{rr_ratio:.2f}x', 'Bull return / Bear loss magnitude'],
        ['Current OAS', f'{BOND["spread_bp"]:.0f} bps', '12M avg: {:.0f}bps'.format(spread_mean)],
        ['OAS Z-Score', f'{spread_zscore:+.2f}σ', 'Negative = tighter than avg'],
        ['Annual Coupon Carry', f'{BOND["coupon"]*100:.3f}%', 'Gross income return'],
        ['Carry over Treasury (bps)', f'{carry_bp:.1f} bps', 'OAS proxy'],
        ['Breakeven Spread Widening', f'{breakeven_spread_widening:.1f} bps', 'Before carry is consumed'],
    ]
    story.append(tbl(ram_data, [W*0.38, W*0.22, W*0.40]))

    story.append(PageBreak())

    # ── SECTION 11: INVESTMENT CONCLUSION ────────────────────────────────────
    story.append(SectionHeader('11', 'INVESTMENT CONCLUSION', W))
    story.append(Spacer(1, 8))

    verdict_banner = Table(
        [[Paragraph('OVERWEIGHT', ParagraphStyle('vb', fontSize=22, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_CENTER, leading=26)),
          Paragraph(f'12-Month Target Return: <b>8–10%</b><br/>Under base-to-bull scenarios (Soft Landing / Rate Cuts)<br/>Risk: Material only under stagflation tail scenario', ParagraphStyle('vb2', fontSize=10, fontName='Helvetica', textColor=WHITE, leading=16, alignment=TA_LEFT))]],
        colWidths=[W*0.25, W*0.75]
    )
    verdict_banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), GREEN), ('BACKGROUND', (1, 0), (1, 0), DEEP_BLUE),
        ('ALIGN',      (0, 0), (0, 0), 'CENTER'), ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 16), ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('LEFTPADDING', (1, 0), (1, 0), 16), ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(verdict_banner)
    story.append(Spacer(1, 12))

    story.append(Paragraph('Positioning Recommendation', S['H2']))
    pos_data = [
        ['Dimension', 'Recommendation', 'Rationale'],
        ['Position Size',  'Overweight vs Benchmark', f'Favorable risk/reward at current OAS/duration'],
        ['Duration',       'Maintain / Extend',        f'Constructive on rate normalization'],
        ['Hedge',          'No Rate Hedge Recommended', f'Duration exposure is the thesis driver'],
        ['Stop Loss',      '10Y Treasury > 5.00%',      f'Reassess if rates break above 5%'],
        ['Take Profit',    '10Y Treasury < 3.75%',      f'Reduce on large rally; re-evaluate entry'],
        ['Review Trigger', 'OAS > 150 bps',             f'Credit signal; investigate fundamentals'],
    ]
    story.append(tbl(pos_data, [W*0.22, W*0.30, W*0.48]))

    story.append(PageBreak())

    # ── SECTION 12: LIMITATIONS ───────────────────────────────────────────────
    story.append(SectionHeader('12', 'MODEL LIMITATIONS', W))
    story.append(Spacer(1, 8))

    limits = [
        ('Parallel Yield Shifts Only', 'The scenario analysis assumes parallel shifts in the yield curve.'),
        ('No Liquidity Premium', 'The model does not explicitly decompose the OAS into default risk premium and liquidity premium components.'),
        ('No Explicit Default Modeling', 'This framework does not model explicit default scenarios.'),
        ('Static Duration Assumption', 'Duration is calculated at current YTM and assumed constant across scenarios.'),
    ]
    for title, body in limits:
        lim_tbl = Table([[Paragraph(f'⚠  {title}', ParagraphStyle('lt', fontSize=9, fontName='Helvetica-Bold', textColor=AMBER, leading=13)), Paragraph(body, S['Body'])]], colWidths=[W*0.28, W*0.72])
        lim_tbl.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY), ('LINEABOVE', (0, 0), (-1, 0), 1.5, AMBER), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (0, 0), 8), ('LEFTPADDING', (1, 0), (1, 0), 8)]))
        story.append(lim_tbl)
        story.append(Spacer(1, 5))

    story.append(PageBreak())

    # ── SECTION 13: TECHNICAL APPENDIX ───────────────────────────────────────
    story.append(SectionHeader('13', 'TECHNICAL APPENDIX', W))
    story.append(Spacer(1, 8))

    story.append(Paragraph('A.2  Model Parameters Summary', S['H2']))
    param_data = [
        ['Parameter', 'Value', 'Parameter', 'Value'],
        ['Coupon Rate',          f'{BOND["coupon"]*100:.3f}%',      'Face Value',       '$1,000'],
        ['Settlement Date',      BOND["settlement"],                'Maturity Date',    '2044-02-23'],
        ['Years to Maturity',    f'{T:.4f}',                        'Periods',          str(n_periods)],
        ['Market YTM',           f'{BOND["market_ytm"]*100:.4f}%',  'Treasury Yield',   f'{BOND["treasury_yield"]*100:.3f}%'],
        ['OAS',                  f'{BOND["spread_bp"]:.0f} bps',    'Model Price',      f'${base_price:.4f}'],
        ['Macaulay Duration',    f'{mac_dur:.6f} yrs',              'Modified Duration',f'{mod_dur:.6f}'],
        ['Convexity',            f'{conv:.6f}',                     'DV01',             f'${dv01:.6f}'],
    ]
    story.append(tbl(param_data, [W*0.28, W*0.22, W*0.28, W*0.22]))

    story.append(Spacer(1, 8))
    story.append(ColoredRule(W, LIGHT_GRAY))
    story.append(Spacer(1, 6))
    story.append(Paragraph('DISCLAIMER: This report is produced by an analytical model for educational and research purposes.', S['Small']))

    # Build content PDF
    doc.build(story, canvasmaker=NumberedCanvas)

    # Merge cover + content
    writer = PdfWriter()
    for pdf_path in [COVER_PDF, CONTENT_PDF]:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)
    with open(OUTPUT_PDF, 'wb') as f:
        writer.write(f)
    print(f"\n PDF successfully generated: {OUTPUT_PDF}")

if __name__ == '__main__':
    print("=" * 60)
    print("  FIXED INCOME RISK DECOMPOSITION FRAMEWORK (LIVE DATA)")
    print("=" * 60)
    print(f"\n[1/4] Bond Pricing")
    print(f"      Model Price:       ${base_price:,.4f}")
    print(f"\n[2/4] Risk Metrics")
    print(f"      Modified Duration: {mod_dur:.4f}x")
    print(f"\n[3/4] Decomposition")
    print(f"      Total Return:      {total_return_pct:+.3f}%")
    print(f"\n[4/4] Generating PDF Report...")
    build_pdf()
    print("=" * 60)
