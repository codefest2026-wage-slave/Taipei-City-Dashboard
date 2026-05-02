## ADDED Requirements

### Requirement: 樣本資料跨越至少六個不同月份
`db-sample-data/check.sql` 的 INSERT 資料列 SHALL 涵蓋至少 6 個不同的 `inspection_date` 月份（格式 `YYYY-MM`），使月趨勢圖在本機可顯示有意義的趨勢曲線。

#### Scenario: 月份數量足夠
- **WHEN** fixture 匯入後執行 `SELECT COUNT(DISTINCT date_trunc('month', inspection_date)) FROM food_safety_inspection_metrotaipei`
- **THEN** 結果 `>= 6`

### Requirement: 每個月份的樣本資料同時包含合格與不合格紀錄
每個月份 SHALL 至少有一筆 `inspection_result = '合格'` 及一筆 `inspection_result = '不合格'` 的資料，使違規率折線在各月份均有非零的分子與分母。

#### Scenario: 指定月份同時含合格與不合格
- **WHEN** 對任一已插入的月份執行 `SELECT DISTINCT inspection_result FROM food_safety_inspection_metrotaipei WHERE date_trunc('month', inspection_date) = '<month>'`
- **THEN** 結果同時包含 `'合格'` 與 `'不合格'`

### Requirement: 兩個城市在多個月份均有資料
`臺北市` 與 `新北市` 兩個城市 SHALL 各自在至少 6 個月份中均有稽查資料，使城市切換後的趨勢圖均能顯示完整曲線。

#### Scenario: 臺北市有足夠月份資料
- **WHEN** 執行 `SELECT COUNT(DISTINCT date_trunc('month', inspection_date)) FROM food_safety_inspection_metrotaipei WHERE city = '臺北市'`
- **THEN** 結果 `>= 6`

#### Scenario: 新北市有足夠月份資料
- **WHEN** 執行 `SELECT COUNT(DISTINCT date_trunc('month', inspection_date)) FROM food_safety_inspection_metrotaipei WHERE city = '新北市'`
- **THEN** 結果 `>= 6`
