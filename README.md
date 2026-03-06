# 📉 Fixed Income Risk Decomposition Engine (Caso Southern Copper Corp 5.875% due to 20245)

Este ecosistema de **Buy-Side Analytics** automatiza la descomposición de riesgos en bonos corporativos de grado de inversión. El motor separa sistemáticamente el **Riesgo de Tasa de Interés** del **Riesgo de Crédito (OAS)**, permitiendo una atribución de valor precisa y la simulación de escenarios macroeconómicos complejos bajo una arquitectura 100% escalable.

> **🎯 Propósito:** Cuantificar la sensibilidad de instrumentos de renta fija ante choques de tipos de interés y spreads, determinando si el valor de un bono responde a factores macro o a la salud crediticia del emisor.

---

## 🔬 Capacidades Analíticas

El framework ha sido validado mediante un análisis profundo del benchmark **Southern Copper Corporation 5.875% due 2045**:

* **Yield Decomposition:** Desglose del Yield-to-Maturity (YTM) en sus componentes de Tasa Libre de Riesgo (Treasury) y Option-Adjusted Spread (OAS).
* **Sensitivity Analysis (Greeks):** Cálculo de Duración de Macaulay, Duración Modificada y Convexidad para modelar la relación no lineal Precio-Rendimiento.
* **Return Attribution:** Análisis waterfall histórico de los últimos 12 meses, descomponiendo el retorno total en impacto de tasas, variaciones de spread e ingresos devengados por cupón.
* **Scenario Stress Testing:** Simulación de escenarios de mercado (Fed Cuts, Recession, Stagflation, Soft Landing) con proyecciones de retorno total y pérdida máxima esperada.

---

## 📊 Insights y Métricas Clave (Southern Copper 2045)

Basado en la valoración cuantitativa realizada con datos de mercado al cierre de **Marzo 2026**:

* **Dominancia de Tasa:** Con una Duración Modificada de **12.39x**, el perfil de riesgo es altamente sensible a la política monetaria. Un choque de +100bps en el YTM genera una contracción de **~12.4%** en el valor de mercado.
* **Riesgo Crediticio:** El OAS actual de **98 bps** presenta un Z-score de **+1.50σ** respecto a su media de 12 meses, indicando un punto de entrada atractivo donde el riesgo corporativo cotiza con un descuento estadístico.
* **Asimetría de Retorno:** * En un escenario de **Aterrizaje Suave**, el motor proyecta un retorno total de **+8.30%**.
    * Ante un escenario de **Estanflación** (choque extremo de +250bps), la pérdida de capital estimada es de **-18.8%**, evidenciando la vulnerabilidad de la parte larga de la curva ante inflaciones persistentes.
* **Carry Analysis:** El cupón del **5.875%** actúa como un ancla de flujo de caja, permitiendo un spread breakeven robusto antes de que la rentabilidad total entre en terreno negativo.

---

## 🛠️ Stack Tecnológico y Lógica de Automatización

El mayor valor de este proyecto es su capacidad de **automatización institucional**, eliminando horas de procesamiento manual en Excel:

* **Ingesta Dinámica:** Conexión vía API a la **Reserva Federal (FRED)** para obtener curvas de tesorería y spreads históricos en tiempo real.
* **Motor Paramétrico:** La herramienta es 100% escalable; basta con modificar un diccionario de parámetros (cupón, vencimiento, emisor) para que el motor recalcule toda la estructura de riesgo en menos de 5 segundos.
* **Anchoring Algorithm:** Algoritmo de anclaje cuantitativo que sincroniza spreads macroeconómicos con el OAS específico del bono para generar análisis de valor relativo coherentes.
* **Reporting "Zero-Touch":** Integración con `ReportLab` para exportar automáticamente los resultados a un reporte PDF profesional o un *Credit Tear Sheet* ejecutivo.

---

## ⚙️ Instalación y Uso

```bash
# Clonar el repositorio
git clone [https://github.com/caballerohh/Fixed-Income-Risk-Analytics-Engine.git](https://github.com/caballerohh/Fixed-Income-Risk-Analytics-Engine.git)

# Instalar dependencias
pip install numpy pandas matplotlib scipy pandas_datareader reportlab pypdf
