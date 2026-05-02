## 1. 擴充 check.sql fixture（多月份資料）

- [x] 1.1 在 `db-sample-data/check.sql` 新增 2024-01 ～ 2024-06 共 6 個月份的 INSERT 資料列，每月各含臺北市與新北市的稽查紀錄
- [x] 1.2 確保每個月份同時包含 `inspection_result = '合格'` 與 `inspection_result = '不合格'` 各至少一筆
- [x] 1.3 驗證：`SELECT COUNT(DISTINCT date_trunc('month', inspection_date)) FROM food_safety_inspection_metrotaipei` 回傳 `>= 6`

## 2. 新增 query_charts 城市變體

- [x] 2.1 在 `db-sample-data/dashboardmanager-demo.sql` 的 `query_charts` COPY 區段新增 `city = 'taipei'` 的 `food_safety_monthly_trend` 紀錄，SQL 過濾 `city = '臺北市'`，回傳月抽檢總量與違規率兩個 `y_axis` 系列，`query_type = 'time'`
- [x] 2.2 新增 `city = 'newtaipei'` 的 `food_safety_monthly_trend` 紀錄，SQL 過濾 `city = '新北市'`，其餘同上
- [x] 2.3 驗證兩筆 SQL 語法正確：可在 `psql` 中直接對 `food_safety_inspection_metrotaipei` 執行並回傳兩個系列（`月抽檢總量`、`違規率(%)`）

## 3. 新增 components 元件紀錄

- [x] 3.1 在 `dashboardmanager-demo.sql` 的 `components` COPY 區段新增 `index = 'food_safety_monthly_trend'` 的元件紀錄，`chart_config` 包含 `"types": ["TimelineSeparateChart"]`、`"color": ["#3D8BFF", "#FF7043"]`、`"unit": "件"` 等欄位
- [x] 3.2 確認 `chart_config` JSON 格式與現有元件紀錄一致（欄位完整、型別正確）

## 4. 綁定 dashboard_components

- [x] 4.1 在 `dashboardmanager-demo.sql` 的 `dashboard_components` COPY 區段新增一筆紀錄，將步驟 3.1 的元件綁定至 `dashboard_id = 1200`（食安儀表板）

## 5. 本機驗證

- [ ] 5.1 重建本機資料庫（`docker-compose -f docker/docker-compose-db.yaml up -d`）並匯入兩份 fixture
- [ ] 5.2 開啟 `http://localhost:8080`，進入食安儀表板，確認 `月度稽查趨勢` 元件出現
- [ ] 5.3 切換城市下拉選單（臺北市 / 新北市），確認折線圖資料隨之更新
- [ ] 5.4 確認藍線（月抽檢總量）與橘線（違規率%）均正常顯示於 6 個月份
