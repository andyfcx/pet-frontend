# Biometeo Frontend 使用說明

這是一個桌面應用程式，為 Python 套件 `biometeo` 提供好用的圖形介面：選擇熱舒適度函式、填入參數（或匯入 CSV）、執行計算，並匯出結果。

## 安裝方式

**方式一：pip / uv**

```bash
pip install biometeo-frontend
biometeo-front
```

**方式二：原生安裝程式**

到專案的 [GitHub Releases](https://github.com/andyfcx/pet-frontend/releases) 頁面下載 macOS `.dmg` 或 Windows 安裝程式並執行，不需要另外安裝 Python。

> macOS 版本目前只有 ad-hoc 簽章。第一次開啟若被 Gatekeeper 擋下，請在 App 上按右鍵選擇「開啟」。

## 基本操作流程

1. **選擇函式**——從下拉選單中選擇 `mPET`、`mPET_quick`、`PET`、`Tmrt_calc`、`PMV`、`SET`、`UTCI` 其中之一。右側的「Documentation」會顯示該函式的說明文件，左側的輸入表單也會依照該函式的參數自動更新，並分類成：
   - Date/Time & Location（日期時間與位置）
   - Physiological Info（生理資訊）
   - Meteorological Data（氣象資料）
   - Other Parameters（其他參數）

   標示 `*` 的欄位為必填，選填欄位會在標籤旁顯示預設值。

2. **輸入資料**，可以擇一方式：
   - 直接在表單中填寫，再按 **Run**；或
   - 點擊 **Open CSV**（或直接把 `.csv` 檔拖進拖曳區）批次處理多筆資料。CSV 的欄位名稱必須對應函式的參數名稱，若缺少必要欄位，程式會先提示錯誤再執行。

3. **檢視結果**——結果會顯示在下方表格中，點擊任一儲存格可將該值複製到剪貼簿。

4. **匯出結果**——從 **Format** 下拉選單選擇 `csv` 或 `json`，再點 **Save Output**（存成檔案）或 **Copy to Clipboard**（複製到剪貼簿）。**Clear** 可清空表格與輸出狀態。

5. **引用建議**——執行完成後，表格下方會顯示該函式建議引用的文獻（若適用，還會附上風速折減指數的說明）。

## 魚眼照片 → 天空可視因子與遮蔭（僅限 Tmrt_calc）

選擇 `Tmrt_calc` 時，表單上方會出現可展開/收合的「Fisheye Photo → Sky View Factor」區塊，用魚眼照片自動算出天空可視因子（`OmegaF`），並提供指定時間的遮蔭狀態（`Is_Shaded`）。

1. 點擊區塊標題展開它。
2. **Select Fisheye Photo** 選擇照片，或直接把照片拖曳到畫布上。
3. 設定 **Date（日期）**、**Latitude（緯度）**、**Longitude（經度）**、**Timezone（時區）**。
4. （選用）拖曳中心點可移動校正圓、拖曳橘色控制點可調整半徑——這個校正只是預覽用，**不會影響**實際的 SVF 計算結果。**Apply Values** 會套用手動輸入的中心座標/半徑數值；**Reset to Auto-Detect** 會還原成自動偵測到的圓。
5. 點擊 **Run Analysis**。完成後：
   - **SVF** 數值會以醒目顏色顯示，同時顯示天空遮罩（sky mask）、太陽路徑疊圖（sun-path overlay），以及日照/遮蔭/可視時間統計。
   - 下方會畫出「Daily Shading Timeline」遮蔭時間軸圖表，把滑鼠移到遮蔭區段上可以看到起訖時間與持續時長。
   - 計算出的 SVF 會**自動填入 `OmegaF`**；系統也會依表單的 `hour_of_day` 找到對應分鐘，並填入 `Is_Shaded`。若分析後修改時間，按下 **Run** 時會再同步一次。
6. 想更換照片時，點擊魚眼區塊的 **Clear** 按鈕——會清空畫布與分析結果，讓你可以放入新的照片。
7. 想移除照片產生的數值，點擊 `OmegaF` 欄位旁的 **Clear Photo Values**；這會清空 `OmegaF` 並將 `Is_Shaded` 重設為 false。
8. **Export Shading Intervals CSV** / **Export Timeline Image** 可以把遮蔭分析結果匯出成檔案。

## 小提醒

- 切換到其他函式再切回 `Tmrt_calc`，先前的魚眼分析結果會保留，並重新套用 `OmegaF` 與符合當前時間的 `Is_Shaded`。
- 拖曳檔案（照片或 CSV）需要應用程式支援拖放功能；如果你使用的版本沒有這項支援，改用 **Select** / **Open CSV** 按鈕即可。
