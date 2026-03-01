# 📉 Fixed Income Risk Decomposition Engine

Este ecosistema de **Buy-Side Analytics** automatiza la descomposición de riesgos en bonos corporativos de grado de inversión. El motor separa sistemáticamente el **Riesgo de Tasa de Interés** del **Riesgo de Crédito (OAS)**, permitiendo una atribución de valor precisa y la simulación de escenarios macroeconómicos complejos.

> **🎯 Propósito:** Cuantificar la sensibilidad de los instrumentos de renta fija ante choques de tipos de interés y spreads, determinando si un bono cotiza bajo par por factores de mercado o deterioro crediticio.

---

## 🔬 Capacidades Analíticas

El framework realiza un análisis profundo sobre benchmarks corporativos (ej. Apple Inc. Senior Notes 2044):

* **Yield Decomposition:** Desglose del Yield-to-Maturity (YTM) en sus componentes de Tasa Libre de Riesgo (Treasury) y Option-Adjusted Spread (OAS).
* **Sensitivity Analysis (Greeks):** Cálculo de Duración de Macaulay, Duración Modificada y Convexidad para modelar la relación no lineal Precio-Rendimiento.
* **Return Attribution:** Análisis waterfall de los últimos 12 meses, descomponiendo el retorno total en impacto de tasas, compresión de spreads e ingresos por cupón.
* **Scenario Stress Testing:** Simulación de escenarios de mercado (Fed Cuts, Recession, Stagflation, Soft Landing) con proyecciones de retorno total a 12 meses.


---

## 📊 Insights y Métricas Clave (Feb 2026)

* **Dominancia de Tasa:** Con una Duración Modificada de **11.85x**, el perfil de riesgo está dominado por la sensibilidad a tipos (shock de 100bps = ~10.9% de cambio en valor).
* **Riesgo Crediticio:** El OAS actual de **73 bps** muestra un Z-score de **-1.19σ**, indicando spreads históricamente ajustados en relación a su media.
* **Asimetría de Retorno:** En un escenario de recorte de tasas (100bps), el motor proyecta un retorno total de **+20.6%**, frente a una pérdida de **-19.6%** en un escenario de estanflación.
* **Carry Analysis:** Identificación de un breakeven de ampliación de spread de **1185 bps** antes de que el carry del cupón sea consumido.

---

## 🛠️ Stack Tecnológico y Lógica

* **Valuation Engine:** Construcción de flujos de caja semi-anuales y cálculo de precios mediante descuento dinámico de flujos.
* **Risk Modeling:** Modelado de la relación precio-rendimiento mediante derivadas de primer y segundo orden (Duración vs Convexidad).
* **Macro Context:** Integración de la curva de tesorería de EE. UU. (1M a 30Y) para el cálculo de spreads y benchmarks de referencia.
* **Tecnologías:** Python (Numpy para cálculo actuarial, Pandas para series de tiempo, Matplotlib para curvas de rendimiento).

---

## ⚙️ Instalación

```bash
# Clonar el repositorio
git clone [https://github.com/caballerohh/Fixed-Income-Risk-Analytics-Engine.git](https://github.com/caballerohh/Fixed-Income-Risk-Analytics-Engine.git)

# Instalar dependencias
pip install numpy pandas matplotlib seaborn
