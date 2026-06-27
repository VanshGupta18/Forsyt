## 1. The GPR Index Features (Sub-Indexes)
Caldara and Iacoviello organized their geopolitical search framework into eight categories, which they aggregated into distinct features:

*   **Geopolitical Threats (GPRT):** This feature captures *anticipated* conflicts and tensions. It aggregates five categories:
    1. War Threats
    2. Peace Threats (e.g., failing negotiations, ceasefire violations)
    3. Military Buildups
    4. Nuclear Threats
    5. Terror Threats
*   **Geopolitical Acts (GPRA):** This feature captures *actual, realized* conflicts. It aggregates three categories:
    6. Beginning of War
    7. Escalation of War
    8. Terror Acts
*   **The Benchmark GPR Index:** This is the primary feature that aggregates both Threats (GPRT) and Acts (GPRA) into a single overarching score of geopolitical tension.
*   **Country-Specific GPR (GPRHC):** The researchers extended their methodology to calculate risk indices specifically targeted at, or originating from, individual countries (such as India, the USA, or Russia).

## 2. Applications Demonstrated in their Research Papers
To prove the usefulness of these features, the authors applied them to several economic models across their papers.

### A. Macroeconomic Forecasting (2022 Paper)
*   **Impact on Investment and Employment:** They used standard Vector Autoregression (VAR) models to demonstrate that spikes in the GPR index systematically foreshadow declines in aggregate corporate investment and national employment rates. 
*   **Economic Disaster Probability:** They proved mathematically that higher geopolitical risk correlates with a higher probability of severe economic downturns and larger downside risks to the global economy.
*   **Firm-Level Capital Expenditures:** By merging the GPR index with individual company data (extracted from earnings calls), they showed that firms heavily exposed to high geopolitical risk actively delay or reduce their capital expenditures.

### B. Financial Market Modeling (2026 AI-GPR Paper)
In their 2026 follow-up paper, the authors replaced their keyword-search method with a Large Language Model (GPT-4o-mini) to measure the semantic intensity of risk. They applied this new "AI-GPR" index to financial markets:
*   **Stock Market Returns:** They applied the AI-GPR index to model equity markets, proving that an intensity-graded risk score improves the accuracy of estimating the negative effect of geopolitical shocks on stock returns.
*   **Oil Supply Disruption Tracking:** By adding a second classification layer to the AI-GPR index, they mapped geopolitical events specifically to the energy sector, producing a historical time series that isolates geopolitical shocks driving regional oil supply disruptions.
*   **Directed Geopolitical Networks:** Using a third classification layer, they applied the index to network theory. They mapped the interactions between geopolitical actors during historical crises, categorizing specific countries as initiators, respondents, or spillover nations. 

To implement these applications in financial market modeling, Caldara and Iacoviello essentially used the GPR features as quantitative inputs (independent variables) in established econometric and machine learning frameworks. Because the GPR indexes reduce complex global news into continuous numerical time series (e.g., a score of 120 on a given day), they can be mathematically correlated with stock prices, oil prices, and volatility.

Here is exactly how these features are implemented to model financial markets:

### 1. Vector Autoregression (VAR) for Market Shocks
In traditional financial economics (as seen in their 2022 paper), the authors use Vector Autoregression models. A VAR model is a statistical system that captures the linear interdependencies among multiple time series.
*   **Implementation:** They create a system of equations where the dependent variables are macroeconomic indicators (like stock market returns, capital investment, or employment rates). The **GPR index** is fed into the system as an exogenous shock variable. 

*   **The Result:** The VAR model calculates an "impulse response function." This mathematically isolates exactly how much a sudden spike in the GPR score causes the stock market to drop in the subsequent days or months, controlling for other variables like interest rates or inflation. 


### 2. Gaussian Process Regression (GPR) and Machine Learning

When modern researchers and financial analysts (including Caldara's later AI extensions) model stock market volatility, they use the Geopolitical Risk index as a feature in predictive algorithms like Random Forests, XGBoost, or Neural Networks.
*   **Implementation:** The dataset is structured so that the target variable (Y) is the future realized volatility of a stock index (like the S&P 500 or Nifty 50). The input features (X) include the **GPR Threat (GPRT)** score, **GPR Act (GPRA)** score, and moving averages of the GPR index from the previous days.
*   **The Result:** The model learns non-linear patterns. For example, it might learn that if the GPR Threat index crosses a certain threshold while the stock market is already in a downtrend, extreme volatility is highly probable in the next 5 days.

### 3. Firm-Level Cross-Sectional Regressions
To analyze how geopolitical risk impacts specific industries or companies, the authors implemented cross-sectional regressions.

*   **Implementation:** They calculated the "beta" (sensitivity) of specific stock sectors to the aggregate GPR index. Simultaneously, they ran textual analysis on individual companies' quarterly earnings call transcripts to count how often executives mentioned geopolitical risk.

*   **The Result:** They regress the firm's capital investment or stock performance against its GPR sensitivity. This proves that companies with high GPR betas (like defense contractors or international shipping firms) react much more aggressively to GPR spikes than domestically insulated companies.