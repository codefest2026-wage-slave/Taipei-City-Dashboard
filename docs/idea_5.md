# Idea 5 — 勞動福祉儀表板

## 主題
整合台北市與新北市勞動市場、社福資源資料，協助政府掌握就業結構、勞動條件與社福分布，
輔助政策制定並提升市民生活保障。

---

## UI 組件設計（共 4 組件）

### 組件 1｜社福與就業服務據點地圖（地圖圖層）
**類型**：空間地圖（Leaflet / Mapbox）

呈現台北、新北社福中心、就業服務站、勞工體檢醫院的地理分布，
支援分類篩選與行政區熱力圖，直觀識別資源分配不均的空白區。

| 資料集 | 城市 | 連結 |
|--------|------|------|
| 臺北市生活危機服務_臺北市社會福利服務中心 | 台北 | https://data.taipei//api/dataset/ece023db-a5f8-4399-97da-f04d7f4009e3/resource/1a2d417e-c121-4a12-835f-97ee6852c4b8/download |
| 新北市政府所屬就業服務據點 | 新北 | https://data.ntpc.gov.tw/api/datasets/4427db9f-2eb0-4646-a291-e6031d564c4f/json |
| 新北市社會福利服務中心名冊 | 新北 | https://data.ntpc.gov.tw/api/datasets/a3b33006-44e2-4a88-959e-af24e7346d2d/json |
| 新北市勞工體格及健康檢查指定醫院 | 新北 | https://data.ntpc.gov.tw/api/datasets/87044f1f-3ec2-4811-af5a-c1dd4bb9460e/json |

---

### 組件 2｜就業結構分析（多維長條 / 堆疊圖）
**類型**：互動式長條圖 + 時序折線圖

呈現新北市就業人口的年齡、教育程度、行業別、職業類別結構，
搭配台北市就業人口職業分佈，比較雙北勞動市場特性。

| 資料集 | 城市 | 連結 |
|--------|------|------|
| 就業者年齡結構 | 新北 | https://data.ntpc.gov.tw/api/datasets/c285509a-7fb2-434f-8542-0b4986c337a8/json |
| 就業者教育程度結構 | 新北 | https://data.ntpc.gov.tw/api/datasets/b77beb94-131a-4c54-a02d-cee19a09f7f2/json |
| 就業者行業結構－服務業 | 新北 | https://data.ntpc.gov.tw/api/datasets/c839a9a7-3a90-48a5-8a55-467399e1fb11/json |
| 就業者行業結構－農業及工業 | 新北 | https://data.ntpc.gov.tw/api/datasets/115a9981-0f3a-4b5b-affc-35019d833309/json |
| 就業者職業結構 | 新北 | https://data.ntpc.gov.tw/api/datasets/957d9a08-5580-459e-a4d7-82dcd5075dc1/json |
| 臺北市就業人口之職業（100年以後） | 台北 | https://data.taipei（統計處）|
| 臺北市勞工保險及就業服務按月別 | 台北 | https://tsis.dbas.gov.taipei/statis/webMain.aspx?sys=220&ymf=8701&kind=21&type=0&funid=a04001001&cycle=1&outmode=12&compmode=0&outkind=1&deflst=2&nzo=1 |

---

### 組件 3｜勞動條件與職災監測（KPI 卡片 + 趨勢圖）
**類型**：數值 KPI 卡片 + 時序折線圖

追蹤台北市職業災害件數、勞資爭議案量、資遣人數等關鍵勞動條件指標，
點選年度可展開細項（行業別、事由別），協助勞政單位預警勞動風險。

| 資料集 | 城市 | 連結 |
|--------|------|------|
| 臺北市勞工重大職業災害 | 台北 | https://tsis.dbas.gov.taipei/statis/webMain.aspx?sys=220&ymf=8400&kind=21&type=0&funid=a05007201&cycle=4&outmode=12&compmode=0&outkind=1&deflst=2&nzo=1 |
| 臺北市勞工資遣解僱概況 | 台北 | https://tsis.dbas.gov.taipei/statis/webMain.aspx?sys=220&ymf=10100&kind=21&type=0&funid=a05006901&cycle=4&outmode=12&compmode=0&outkind=1&deflst=2&nzo=1 |
| 臺北市政府勞動局勞工歷年申訴服務中心成果 | 台北 | https://data.taipei//api/dataset/b897366a-88ae-4c04-9181-74ec6bd815fb/resource/076112f6-86e2-4566-adb3-558c0ba2e002/download |
| 勞工(農民)保險及勞資爭議 | 新北 | https://data.ntpc.gov.tw/api/datasets/a8542567-894f-4674-88fe-c794918cf3a0/json |
| 臺北市事業單位勞工檢查次數（82年以後） | 台北 | https://tsis.dbas.gov.taipei/statis/webMain.aspx?sys=220&ymf=8200&kind=21&type=0&funid=a05007002&cycle=4&outmode=12&compmode=0&outkind=1&deflst=2&nzo=1 |
| 臺北市勞工保險投保概況 | 台北 | https://tsis.dbas.gov.taipei/statis/webMain.aspx?sys=220&ymf=5700&kind=21&type=0&funid=a05006201&cycle=4&outmode=12&compmode=0&outkind=1&deflst=2&nzo=1 |

---

### 組件 4｜社福資源利用與弱勢扶助（圓餅 / 表格）
**類型**：分類圓餅圖 + 可篩選資料表

呈現低收入戶、身心障礙、急難救助、居家服務等社福申請量與核准率，
並整合職業訓練與就業輔導資料，反映弱勢族群自立支援成效。

| 資料集 | 城市 | 連結 |
|--------|------|------|
| 社會福利統計_臺北市低收入戶及中低收入戶申請 | 台北 | https://data.taipei//api/dataset/9d7f800d-33b9-44cb-8c5b-187cb00c017e/resource/e273f45d-5b8c-4ffd-b4f0-ddacd1dbde66/download |
| 社會福利統計_臺北市急難救助 | 台北 | https://data.taipei//api/dataset/926f8d82-98a4-45a6-9f49-149aa64ad3a9/resource/97f648fc-d0ad-486d-a824-98549bbc6463/download |
| 社會福利統計_臺北市居家服務 | 台北 | https://data.taipei//api/dataset/bd7914c1-a33c-4d40-815f-25fd72a114d6/resource/ed437ab9-9536-4b64-9e1e-82808225cafa/download |
| 社會福利統計_臺北市身心障礙者生活補助申請 | 台北 | https://data.taipei//api/dataset/9f513f50-9af8-4d3e-9074-2226804fddbd/resource/ff7778d4-0921-4a94-948d-095e69232a6c/download |
| 社會福利統計_臺北市低收入戶暨中低收入戶自立脫貧服務 | 台北 | https://data.taipei//api/dataset/a3f23233-88a9-4e15-b45f-49d41e71d496/resource/1f945d54-4180-4cef-9f9b-b5c313b522e1/download |
| 就業輔導 | 新北 | https://data.ntpc.gov.tw/api/datasets/c4831dc1-fa82-480d-b9d0-dcf2da2532df/json |
| 職業訓練 | 新北 | https://data.ntpc.gov.tw/api/datasets/00dde8df-2fd9-4c48-8c44-bb54418ec09a/json |
| 臺北市職業訓練人數概況 | 台北 | https://data.taipei//api/dataset/c128c15a-34f4-4cd7-ae81-8cf8a77c33dc/resource/7850cf21-31a5-4611-9430-8d45fdc86a7f/download |

---

## 組件互動設計

- **地圖組件**篩選行政區後，同步過濾其他三個組件顯示對應區域數據
- **就業結構組件**支援年度切換，對比疫情前後就業結構變化
- **勞動條件組件**設置異常值警示（如職災件數超過前三年均值 120%）
- **社福資源組件**可切換「申請量」與「核准率」兩種檢視視角

## 政策應用價值

| 面向 | 應用場景 |
|------|----------|
| 就業促進 | 識別就業服務站分布與就業缺口，優化資源配置 |
| 勞動保護 | 職災熱區預警，優先排定勞檢頻率 |
| 社會安全網 | 追蹤低收入戶脫貧進度，評估現金補助成效 |
| 弱勢培力 | 串聯職訓與就業輔導，提升自立就業率 |

---

## 過濾紀錄（對照 Taipei City Dashboard）

無移除項目。

說明：
- 組件2 就業結構分析：涵蓋全年齡層就業人口的年齡、教育、行業別結構，與 Dashboard「高齡就業人口之年增結構」（單一族群、增量視角）不同，保留
