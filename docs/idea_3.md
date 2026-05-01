# Idea 3：永續環境儀表板

## 主題
整合空氣品質、再生能源、碳排放與廢棄物管理資料，呈現雙北城市永續發展現況，協助政府推動低碳政策並引導市民參與環境保護行動。

---

## UI 組件設計（4 組件）

### 組件 1｜地圖：空氣品質感測站與淨化區空間分布（含地圖圖層）

**類型：** 互動式地圖（Leaflet / Mapbox）

**說明：**
以地圖疊加雙北各區 AQI 微型感測站點位，標記點依即時 AQI 數值以顏色區分（綠/黃/橘/紅），同時顯示新北市空氣品質淨化區範圍作為綠色圖層，讓使用者一眼辨識高污染與高綠覆率區域的空間關係。

**使用資料集：**
| 資料集名稱 | 來源 | 用途 |
|---|---|---|
| 臺北市空氣品質微型感測器屬性資料 | data.taipei | 感測站點位（經緯度） |
| 臺北市空氣品質微型感測資料 | data.taipei | 即時 AQI 數值 |
| 新北市空氣品質人工監測站位置 | data.ntpc.gov.tw | 新北監測站點位 |
| 新北市空氣品質資訊 | data.ntpc.gov.tw | 新北即時 AQI |
| 新北市空氣品質淨化區 | data.ntpc.gov.tw | 綠化區多邊形圖層 |

**API：**
- `https://data.taipei//api/dataset/ca73fa24-5900-463c-b427-f648148c6827/resource/a45d7443-bce1-405e-abe9-198fe539bf9d/download`
- `https://data.taipei//api/dataset/db8b7f27-6139-43a7-addb-f45f122a47b0/resource/78db2405-cac4-4100-9a8f-a6739d883afa/download`
- `https://data.ntpc.gov.tw/api/datasets/a57c5c06-5066-4452-b2f2-9cfc95d4291d/json`
- `https://data.ntpc.gov.tw/api/datasets/e413ec2b-986e-46d0-8cbd-2223cba8ca06/json`
- `https://data.ntpc.gov.tw/api/datasets/42d5f96b-c6f6-445a-a259-48c270b384e6/json`

---

### 組件 2｜折線圖：再生能源裝設量歷年趨勢

**類型：** 多系列折線圖（Plotly / ECharts）

**說明：**
呈現台北市太陽能、風能等再生能源核准裝設量的年度趨勢，並疊加再生能源憑證案場累積統計，讓決策者追蹤綠能政策推動成效。可切換「核准量 vs. 實裝量」雙指標比較。

**使用資料集：**
| 資料集名稱 | 來源 | 用途 |
|---|---|---|
| 臺北市再生能源發電設備之核准資料 | data.taipei | 歷年核准設備明細 |
| 臺北市再生能源設置資料 | data.taipei | 實際設置地點與容量 |
| 臺北市政府產業局再生能源憑證案場統計 | data.taipei | 憑證案場累積數量 |

**API：**
- `https://data.taipei//api/dataset/67c48cb8-a911-4122-a2e4-a6c217cc872a/resource/24956560-d5e0-48bb-8c59-8c0e2cf2b287/download`
- `https://data.taipei//api/dataset/26e04fb7-ea13-44d1-8a2e-8598cca6fd9c/resource/293b49ab-01ad-45b1-988e-3488727ca005/download`
- `https://data.taipei//api/dataset/70d2e6ec-14ab-4e04-bc33-bb29bf9290c9/resource/543fb157-b8f6-42e8-99fd-1a3163dee92b/download`

---

### 組件 3｜指標卡片組：碳排放與低碳認證進度

**類型：** KPI 卡片 + 進度條（Dashboard Cards）

**說明：**
展示三大低碳指標：
1. **每度水 CO₂ 排放量**：台北市用水碳足跡當量，呈現節水即減碳的觀念。
2. **低碳永續家園認證數**：台北市各行政區通過低碳認證的里數，以進度條呈現達標率。
3. **用電大戶排行**：台北市用電量前N名對象清單，搭配節電對比提示。

**使用資料集：**
| 資料集名稱 | 來源 | 用途 |
|---|---|---|
| 臺北市每度水排放二氧化碳(CO2)約當量 | data.taipei | 用水碳排係數 |
| 臺北市低碳永續家園計畫本市認證執行情形 | data.taipei | 各區里認證進度 |
| 臺北市用電大戶資料 | data.taipei | 高耗電對象名冊 |

**API：**
- `https://data.taipei//api/dataset/a7ef99ef-21a3-4806-a264-512ff9ffcd6c/resource/52de4b17-234c-44f5-9312-245381f9d9f3/download`
- `https://data.taipei//api/dataset/ba984f2b-0867-4e3d-90f5-ac191444a2f9/resource/72909622-3154-4451-85d8-d9cdd9ab330f/download`
- `https://data.taipei//api/dataset/67d1474b-b236-4c1c-b56f-2e12d852688b/resource/24e819b3-c158-4565-b955-286e1b0ed1e3/download`

---

### 組件 4｜長條圖：廢棄物清運與焚化廠負荷分析

**類型：** 分組長條圖 + 表格（Bar Chart + Data Table）

**說明：**
以台北市歷年各區隊清運垃圾量（含堆肥、廚餘）製作分組長條圖，呈現廢棄物總量年度變化趨勢；搭配新北市焚化廠運作資料，顯示焚化處理量與廠區負荷，讓市民了解廢棄物去向並促進減量意識。

**使用資料集：**
| 資料集名稱 | 來源 | 用途 |
|---|---|---|
| 臺北市歷年各區隊清運垃圾、堆肥、養豬 | data.taipei | 各年度清運量 |
| 臺北市巨大垃圾統計 | data.taipei | 大型廢棄物量 |
| 新北市垃圾焚化廠位置 | data.ntpc.gov.tw | 焚化廠地點 |
| 新北市八里垃圾焚化廠營運管理 | data.ntpc.gov.tw | 焚化處理量 |

**API：**
- `https://data.taipei//api/dataset/4363ed33-6f01-420c-aef7-acb016ee3eef/resource/683f30f8-5313-4ab3-8133-75a8c9f782fa/download`
- `https://data.taipei//api/dataset/25ba5cd2-8dab-4fce-bac8-c13a72863ed6/resource/55a77e88-1949-4766-b451-3bf60d97b5fb/download`
- `https://data.ntpc.gov.tw/api/datasets/39e17852-9ac9-45b7-bc60-d8d0ed7e3161/json`
- `https://data.ntpc.gov.tw/api/datasets/fdfdc704-ca66-4735-99fe-3dfb1f79efb7/json`

---

## 組件關聯說明

```
空氣品質地圖（組件1）
    ↕ 空間感知：哪裡污染嚴重、哪裡綠化充足
再生能源趨勢（組件2）
    ↕ 政策進展：綠能裝設是否改善空氣品質
碳排指標卡（組件3）
    ↕ 成果驗證：用電/用水碳排與低碳認證相互呼應
廢棄物分析（組件4）
    ↕ 行動引導：減量成效督促市民參與資源回收
```

四組件共同建構「環境現況→能源轉型→碳排追蹤→廢棄物管理」的完整永續敘事鏈。

---

## 過濾紀錄（對照 Taipei City Dashboard）

無移除項目。

說明：
- 組件1 使用**微型感測器**資料（臺北市空氣品質微型感測器）及**空氣品質淨化區**圖層，與 Dashboard「空氣品質」（標準 EPA 監測站）屬不同資料層次，保留
- 組件3 碳排指標：每度水 CO₂ 排放量與低碳認證進度與 Dashboard「溫室氣體排放統計」（總量統計）角度不同；用電大戶排行與「用電量統計」（總量）視角亦不同，保留
