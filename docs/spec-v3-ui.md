# Спека главного окна VideoBoost v3 (WinUI 3, Mica «жидкое стекло»)

Дата: 07.11.2026 · Версия: **v3.1 (объединённая редакция)** · Статус: **утверждена владельцем 07.11.2026**
Автор спеки: ux-designer. Следующий шаг: `ui-dev` верстает `Views/`, `engine-dev` — пайплайн.
Все имена контролов в спеке — это `x:Name`; применяются в разметке 1:1. Запрещены возвраты
Expander/самодельных канвасов и запрет Dark-only без решения владельца (см. §11 и «Историю утверждений»).

---

## 0. Цель

Одно окно VideoBoost v3 на WinUI 3, полностью на **системном Fluent** — никаких самодельных
канвасов, перекрытий и «пилюль по координатам» (боли прошлой эпохи). Фич-паритет с legacy 1:1,
новый концепт: Mica-окно, стеклянные карточки, ≤ 3 действия до результата
(файл → пресет → «Начать обработку»), 4 состояния у каждой зоны. Тема — Dark **и** Light (§3).

---

## 1. Информационная архитектура окна v3

### 1.1 Регионы и размеры (типовое окно 1100×900, minsize 960×784)

| Регион | Высота @1100×900 | Приоритет | Содержимое |
|---|---|---|---|
| `Titlebar` (кастомный) | 44 px | средний | иконка + «VideoBoost» (Title 20) + подзаголовок Caption 12; справа системные caption-кнопки |
| `NotificationBar` (InfoBar, единственный экземпляр) | auto (0/48) | высокий | транзитные события: скачивание инструментов, готово, ошибка |
| **Тело — 2 колонки 58 : 42, зазор 12** | ~700 px | — | — |
| └ `VideoCard` (левая) | * (min 240) | 1 | drop-зона + список видео |
| └ `RunCard` (левая) | auto (~200) | 2 | прогресс-блок + кнопки |
| └ `SettingsCard` (правая) | * по контенту; ScrollViewer — страховка | 1 | пресеты + **8 строк настроек, всегда видны** (ScrollViewer активен только при дефиците высоты, см. §9а) |
| `BottomStrip` | 36 px | средний | статус инструментов + «Скачать / проверить инструменты» + тумблер журнала |
| `JournalPanel` | 150 px (открыт) / 0 | низкий | журнал; авто-раскрытие при старте/ошибке |

- Колонки: `ColumnDefinition MinWidth="520"` (левая) и `MinWidth="336"` (правая) → при 960 ничего
  не перекрывается; правая при дефиците высоты уходит под ScrollViewer.
- Отступы окна: 16 по бокам, 12 сверху тела, зазор 12 между колонками.
- Решение «Добавить видео»: **drop-зона с пустым состоянием** (не строка) — она же площадка
  drag&drop, она же заглушка пустого списка. При ≥1 файле зона сворачивается в компактную
  «полку добавления» 40 px над списком.
- Решение «журнал»: **полоса всегда видна (36 px) + панель 150 px раскрывающаяся**.
  Авто-раскрытие при старте обработки и при ошибке; вручную — кнопка с шевроном.
- Решение «сворачиваемые настройки»: **нет** (утверждено владельцем, дельта v3.1). Нативный
  `Expander` не используется: все 8 настроек видимы подряд; группа «Кодирование и хранение»
  (Кодировщик, Качество, Tile, JPEG) отграничена разделителем `SettingsDivider2` +
  Caption-заголовком `EncodeGroupHeader` (финальный текст — ui-copywriter).

### 1.2 XAML-структура (скетч) — `Views/MainWindow.xaml`

```xaml
<Grid x:Name="RootGrid" Background="{ThemeResource VbBackdropBrush}">   <!-- Mica; fallback-токен -->
  <Grid.RowDefinitions>44, Auto, *, Auto, Auto</Grid.RowDefinitions>   <!-- титлбар, уведомление, тело, журнал, полоса -->

  <Grid x:Name="AppTitleGrid">          <!-- титлбар; SetTitleBar(AppTitleGrid), см. §8 -->
    <Image x:Name="AppIcon" Width="20" Height="20"/>
    <TextBlock x:Name="AppTitleText" Text="VideoBoost"/>
    <TextBlock x:Name="AppSubtitleText" Text="улучшение видео и плавности"/>
  </Grid>

  <InfoBar x:Name="NotificationBar" IsOpen="False" TightLayout="True"/>

  <Grid x:Name="BodyGrid" ColumnSpacing="12" Margin="16,12,16,0">
    <Grid.RowDefinitions>*, Auto</Grid.RowDefinitions>
    <Grid.ColumnDefinitions>58*, 42*</Grid.ColumnDefinitions>
    <Grid.ColumnDefinition ... MinWidth="520"/><Grid.ColumnDefinition ... MinWidth="336"/>

    <Border x:Name="VideoCard" Style="{StaticResource GlassCardStyle}">   <!-- карточка 1 -->
      <local:DropVideoCard/>
    </Border>
    <Border x:Name="RunCard">                                            <!-- карточка 3 -->
      <local:RunCard/>
    </Border>
    <Border x:Name="SettingsCard">                                       <!-- карточка 2 -->
      <ScrollViewer><local:SettingsCard/></ScrollViewer>
    </Border>
  </Grid>

  <local:JournalPanel x:Name="JournalPanelBody" Height="150"/>           <!-- Visibility по состоянию -->

  <Grid x:Name="BottomStrip" Height="36">
    <Button x:Name="PrepareToolsButton"/>          <!-- видна, только пока есть что качать -->
    <StackPanel x:Name="ToolsStatusChip">          <!-- Ellipse 8px ToolsDot + TextBlock ToolsStatusText -->
    <Button x:Name="JournalToggle"/> <Button x:Name="ClearLogButton"/>
  </Grid>
</Grid>
```

### 1.3 Структура контролов

```xaml
<!-- DropVideoCard -->
<Border x:Name="VideoDropTarget" Style="DropZoneStyle">   <!-- пустое состояние: иконка + 2 строки -->
  <TextBlock x:Name="DropHintText" Text="Перетащите видео сюда…"/>
</Border>
<Button x:Name="AddVideosButton"/> <Button x:Name="RemoveVideosButton"/> <Button x:Name="ClearVideosButton"/>
<ListView x:Name="VideoList" SelectionMode="Extended"/>   <!-- item: имя (TextTrimming=CharacterEllipsis) + путь (Caption) + FontIcon-удаление -->
<TextBlock x:Name="FilesCountText" Text="Видео не выбраны"/>

<!-- SettingsCard: пресеты + 8 строк, все всегда видны -->
<PillChoice x:Name="PresetPills"/>                        <!-- Быстро/Баланс/Максимально, item 48px: заголовок+подпись -->
<TextBlock x:Name="PresetDescriptionText"/>               <!-- описание пресета, Caption 12 -->
<Border x:Name="SettingsDivider1"/>                       <!-- 1px VbCardEdgeBrush -->
row: <TextBlock "Масштаб" W=96/>    <PillChoice x:Name="ScalePills" Items=5/>      <!-- x2, x3, x4, 4K авто, 8K авто -->
row: <TextBlock "Модель" W=96/>     <PillChoice x:Name="ModelPills" Items=3/>      <!-- Авто, Лёгкая, Тяжёлая -->
row: <TextBlock "Плавность" W=96/>  <ToggleSwitch x:Name="InterpSwitch"/> <PillChoice x:Name="FpsPills" Items=2/> <!-- 60, 120 -->
row: <TextBlock "Тип видео" W=96/>  <PillChoice x:Name="ContentPills" Items=2/>    <!-- Обычное, Аниме -->
<Border x:Name="SettingsDivider2"/>
<TextBlock x:Name="EncodeGroupHeader" Text="Кодирование и хранение"/>  <!-- Caption 12, VbMutedBrush -->
row: <TextBlock "Кодировщик" W=96/> <PillChoice x:Name="EncoderPills" Items=4/>    <!-- Авто, H.264, H.265, CPU -->
row: <TextBlock "Качество" W=96/>   <PillChoice x:Name="QualityPills" Items=4/>    <!-- Авто, Скорость, Баланс, Макс -->
row: <TextBlock "Tile" W=96/>       <PillChoice x:Name="TilePills" Items=4/>       <!-- Авто, 256, 384, 512 -->
row: <ToggleSwitch x:Name="SaveSpaceSwitch"/> <TextBlock "Экономить место: JPEG-промежутки"/>
<TextBlock x:Name="SpeedNoteText"/>                        <!-- предупреждение про RX 570; сразу после SaveSpaceSwitch -->
```

Сетка строк: метка — колонка `Width="96"` (единая ось ±1px), зазор метка↔контроль 12,
вертикальный шаг строк 4/8, разделители — 8/1/8.

---

## 2. Карта контролов WinUI 3 (регламент: один виджет на задачу)

| Задача | Контрол | Источник | `x:Name` |
|---|---|---|---|
| Все пилюльные выборы | **`Segmented`** (CommunityToolkit `CommunityToolkit.WinUI.Controls.Segmented`) в единой обёртке `PillChoice` (Chip-стиль, высота 32; пресеты — 48 с подписью) | NuGet | `PresetPills`, `ScalePills`, `ModelPills`, `FpsPills`, `ContentPills`, `EncoderPills`, `QualityPills`, `TilePills` |
| FPS 60/120 | тот же `Segmented` с 2 айтемами (не ToggleSwitch — не тумблер по смыслу; не RadioButtons — ломает ритм) | | `FpsPills` |
| Плавность, «Экономить место» | нативный `ToggleSwitch` без inline on/off-подписей (текст — в row-метке) | системный | `InterpSwitch`, `SaveSpaceSwitch` |
| Список видео | нативный `ListView` + `DataTemplate` (multi-select) | системный | `VideoList` |
| Drop-зона | нативный `Border` + `DragOver/Drop/DragLeave` (свая логика — только события, не canvas) | системный | `VideoDropTarget` |
| Прогресс | композит `BoostProgressBar` из нативных: `ProgressBar` + `ProgressRing` + % + текст шага + «файл N из M» | системные | `BoostProgress`, `BoostRing`, `BoostPercentText`, `BoostStatusText`, `CurrentFileText` |
| Кнопки | нативные `Button` + стили из токенов | системные | `StartButton` (accent), `CancelButton` (danger), `OpenFolderButton`, `AddVideosButton`, `RemoveVideosButton`, `ClearVideosButton`, `PrepareToolsButton`, `JournalToggle`, `ClearLogButton` |
| Статус инструментов | нижний chip: `Ellipse` 8 px + `TextBlock`; ошибки — уносятся в InfoBar | системные | `ToolsDot`, `ToolsStatusText` |
| Уведомления | нативный `InfoBar` (единственный экземпляр, severity меняется) | системные | `NotificationBar` |
| Подсказки настроек | нативный `ToolTipService.ToolTip` — **все 11 legacy-подсказок 1:1** | системные | — |
| Предупреждение x4/8K (десятки часов на RX 570) | нативный `TeachingTip` (auto при выборе «Максимально» / x4 / 8K-авто) | системные | `TeachingTip8K` |
| Заголовок группы настроек | нативный `TextBlock` (Caption 12, VbMutedBrush) | системные | `EncodeGroupHeader` |
| Разделители | нативный `Border` 1 px `VbCardEdgeBrush` | | `SettingsDivider1`, `SettingsDivider2` |
| Журнал | виртуализованный `ItemsControl`/`ListView` (`JournalLines`) + TextBlock с цветом по severity (не TextBox — нужен цвет строки); авто-скролл | системные | `JournalLines` |

**Запрет**: `Canvas` и self-drawn пиксели; на карточку — один стиль (`GlassCardStyle`),
на отступы — единая шкала (§3.3). Дубликатов виджетов нет: 8 групп выбора = один `PillChoice`.

---

## 3. Материалы и тема

### 3.1 Mica vs Acrylic (с учётом слабого железа RX 570)

- Окно: **`MicaBackdrop` (Kind BaseAlt)** — действует в **обеих темах**; WinUI сам рендерит
  Light/Dark Mica по системной теме, дополнительные настройки не нужны. Дешевле Acrylic:
  статичная композитная, нагрузка не растёт на слабом GPU.
- Карточки — стеклянные `Border` поверх Mica в полупрозрачном фоне (LayerFill ~70%) —
  даёт «стекло» без второй Acrylic.
- Acrylic — только на 1–2 **нативных** оверлеях (`TeachingTip`, `InfoBar` — их Fluent-материалы
  работают в обеих темах сами). Свой `DesktopAcrylicBackdrop` на окно не применяем.

### 3.2 Палитра-ДНК → Fluent-ресурсы (`Themes/UiTheme.xaml`, `ThemeDictionaries Dark` + `Light`)

| Токен | Dark | Light |
|---|---|---|
| `VbBackdropColor` (fallback-фон) | `#070809` | `#F3F6FB` |
| `VbCardBrush` (карточки над Mica) | `#10141B` @72% (`#B810141B`) | белый @70% (`#B2FFFFFF`) |
| `VbCardEdgeBrush` (+ делители) | `#1C2333` | `#DCE1EC` |
| `VbTextColorBrush` | `#E8EEF8` | `#1A2028` |
| `VbMutedBrush` | `#93A3BC` | `#5B6472` |
| Прогресс/кольцо fill (`VbCyan*`) | `#22D3EE` (track = fill @20%) | `#0891B2` (track = fill @20%) |
| Success | `#86EFAC` | `#15803D` |
| Warning | `#FCD34D` | `#B45309` |
| Danger | `#FCA5A5` | `#B91C1C` |
| `SystemAccentColor` (`VbAccentColor`) | `#7C5CFF` | `#7C5CFF` — **не меняется** |
| `VbAccentFillBrush` — заливка CTA/выбранной пилюли | `#6A4BE3` | `#5A3FD9` |
| `VbAccentFillHoverBrush` | `#5F41D6` | `#4C33C4` |
| `VbAccentFillPressedBrush` | `#5236BC` | `#4029A8` |
| Фон панели журнала | `#0F131A` solid | `#99FFFFFF` |
| Текст журнала | `#D6DEEE` | `#1A2028` |

- Маппинг на ключи: `VbCardBrush` → `LayerOnMicaBaseAltFillColorDefaultBrush`;
  `VbCardEdgeBrush` → `CardStrokeColorDefaultBrush` / `DividerStrokeColorDefaultBrush`;
  `SystemAccentColor` и `SystemAccentColorLight1..3 / Dark1..3` — override от `#7C5CFF`;
  `VbCyan*` → `ProgressBarForegroundColor` / `ProgressBarBackgroundColor` /
  `ProgressRingForegroundThemeBrush`; `VbTextColorBrush`/`VbMutedBrush` →
  `TextFillColorPrimary/Secondary/TertiaryBrush`.
- Контраст (замер для Body 14): белый на `#7C5CFF` = **4.35:1 < 4.5 в обеих темах** →
  заливки кнопок «Начать» и выбранных чипов идут через `VbAccentFillBrush`
  (белый-на-фиолетовом: 5.6:1 Dark / 6.7:1 Light; hover/pressed тоже ≥4.5).
  `#7C5CFF` остаётся за `SystemAccentColor`: фокус, selection-кольцо, бордеры, иконки;
  в Dark допустим как цвет ссылок (5.2:1), в Light как цвет текста **не используется** —
  вместо него `#5A3FD9`. `#0891B2` в Light держит ≥3:1 как графический элемент (прогресс).
- Акцент-правило: фиолетовый — интерактив (CTA, выбранная пилюля, ссылки); голубой —
  **только телеметрия** (прогресс, спиннер). Голубой не живёт на кнопках; на вьюпорте
  ≤ 1 фиолетового CTA.
- Правило темы: `RequestedTheme` **не задаётся** — окно следует системной теме; `App.xaml`
  содержит только merge `UiTheme.xaml`; `ThemeDictionaries` обязаны содержать **обa**
  набора (Light и Dark). Ограничение v0.1 (зафиксировано): переключатель темы в UI
  **не добавляется**.

### 3.3 Типографика (Segoe UI Variable) и шкала отступов

| Роль | Ступень | Использование |
|---|---|---|
| Title | 20 SemiBold | заголовок окна в Titlebar |
| SectionTitle | 14 SemiBold | названия карточек, подписи строк настроек, item пресетов |
| Body | 14 regular | основной текст, item списка видео |
| Caption | 12 regular | подпись пресетов, описания, `SpeedNoteText`, `EncodeGroupHeader`, футер |
| Journal | Consolas 12 | строки журнала |

Только системные стили Fluent (`Title/Body/CaptionTextBlockStyle` — наследуем/переопределяем
по этим ступеням; своих кастомных фас не заводим).

Отступы: **4 / 8 / 12 / 16 / 24** px. Внутри карточки — 16 от края; между блоками — 12;
между строками — 4/8; метка↔контроль — 12; между колонками — 12. Никаких «11 против 12».

---

## 4. Состояния экрана

| Состояние | Когда | UI |
|---|---|---|
| **1. Пусто** (нет видео) | окно только открыто, инструменты есть | `DropHintText`: «Перетащите видео сюда… или нажмите Добавить»; `VideoList` пуст; `StartButton` disabled (текст «Начать обработку»); `CancelButton`, `OpenFolderButton` disabled; `JournalPanel` закрыт; статус «Готов к работе» |
| **2. Пусто + нет инструментов** | первый запуск / `tools` отсутствует | `ToolsDot` красный, `PrepareToolsButton` видна; InfoBar warning «Инструменты не найдены — скачаются при запуске»; drop-зона активна (файлы добавлять можно) |
| **3. Готов** (есть видео) | список ≥1 + инструменты готовы | список заполнен, `FilesCountText` «N видео»; `StartButton` enabled, текст «▶ Начать обработку (N)» при N>1; пресет «Баланс» по умолчанию |
| **4. Обработка** | после «Начать» | кнопки: `StartButton` **скрыт со своим слотом** (ряд не прыгает), `CancelButton` доступен (danger); `SettingsCard` и `VideoCard` — `IsEnabled=False` целиком; прогресс: `BoostRing` крутится, `BoostProgress` 0–100%, `BoostPercentText` «37%», `BoostStatusText` «Апскейл 37%» / «Интерполяция…», `CurrentFileText` «Файл 2 из 5»; `JournalPanel` авто-раскрывается; события — через InfoBar |
| **5. Завершено** | все файлы готовы | InfoBar success «Готово: N файлов в папке output»; `OpenFolderButton` enabled (акцентное внимание); прогресс 100%, кольцо остановлено; статус «Готово»; `StartButton` возвращается на слот |
| **6. Ошибка** | хотя бы один файл упал | InfoBar error «Что пошло не так — см. журнал» + красная строка в журнале; `JournalPanel` авто-открыт; состояние возвращается в «Готов»; `StartButton` снова enabled |

**Паузы нет** (паритет 1:1) — только «Отмена»: убивает дерево процессов, чистит temp,
возвращает в «Готов» со списком файлов нетронутым.

Примечание (v3.1): состояния определяются семантикой и **не зависят от темы**; нативные
`InfoBar`/`TeachingTip`/`InfoBadge` не перекрашиваются в обеих темах. Зоны, где работают
Vb-цвета (чип `ToolsDot`, строки журнала, статусы `BoostStatusText`), берут значения из §3.2:
Light — `#15803D / #B45309 / #B91C1C`, Dark — `#86EFAC / #FCD34D / #FCA5A5`. Отдельных
«светлых» переопределений состояний нет.

---

## 5. Потоки пользователя (≤ 3 действия) и крайние случаи

**Поток A — обработка (минимальный путь)**
1. Drop файлов (или «Добавить видео…», или `Delete`-сценарии в списке).
2. Опционально — тап на пресет-пилюлю («Баланс» default; выбор пресета пересеивает
   Масштаб/Модель/FPS/Encoder/Quality/Tile до.defaults — логика legacy `_on_preset_changed`),
   описание пресета под пилюлями обновляется.
3. «▶ Начать обработку (N)» → состояние 4 → «Завершено» / «Отмена».

**Поток B — первый запуск, нет инструментов**
`PrepareToolsButton` → скачивание с прогрессом в InfoBar («Real-ESRGAN: 210 МБ») → готово →
`ToolsDot` зелёный «Инструменты готовы». Файлы добавляются одновременно со скачиванием.

**Поток C — клавиатура**
- `Enter` → `StartButton` (если enabled), `Escape` → `CancelButton` (паритет legacy).
- Tab-порядок: «Добавить → список → пресеты → настройки → Начать → Отмена».

**Поток D — во время обработки**
Весь `SettingsCard` и `VideoCard` заблокированы; drop не принимается — добавление
доступно после завершения.

**Крайние случаи**
- Дубликаты и не-видео при добавлении: молча пропускаем, счётчик пропущенных — в InfoBar
  или в журнал (суммарно поведение legacy `_on_drop`).
- Длинные имена, кириллица/пробелы: `TextTrimming=CharacterEllipsis` на item списка,
  полный путь в ToolInfo `ToolTip` строки; пути только через `Path.Combine`.
- Resize 960 → 1440: колонки остаются 58/42 с MinWidth 520/336, вертикальные адаптации —
  через `TextWrapping` (без legacy `_fit_wrap`/wraplength-хаков); зоны-сжатия — §9(а).
- Выбор x4 / «8K авто» / пресет «Максимально»: `TeachingTip8K` «десятки часов» (мотив:
  RX 570), дальше пользователь решает сам.
- DPI 125–200%: проверки по §9(е).
- InfoBar накладывается как Row Auto — тело reflow-ится, перекрытий нет.

---

## 6. Что меняется в Views/ (файлы 1:1)

| Файл | Назначение |
|---|---|
| `Views/MainWindow.xaml(.cs)` | Full-bleed shell: `Titlebar`, `NotificationBar`, `BodyGrid` (58/42), `JournalPanel`, `BottomStrip`; перехват Enter/Escape |
| `Views/Controls/DropVideoCard.xaml(.cs)` | drop-зона + `VideoList` + кнопки + счётчик + заглушка пустого состояния |
| `Views/Controls/SettingsCard.xaml(.cs)` | пресеты + 8 строк настроек (Divider1/Divider2, `EncodeGroupHeader`, `SpeedNoteText`) |
| `Views/Controls/RunCard.xaml(.cs)` | кнопки + `BoostProgress` (ProgressBar + Ring + % + шаг/файл N из M) + статус |
| `Views/Controls/JournalPanel.xaml(.cs)` | `JournalLines` (виртуализованный, авто-скролл) + «Очистить» + пустое состояние |
| `Views/Controls/PillChoice.xaml(.cs)` | единая обёртка над `Segmented` (Chip-стиль 32/48), переиспользуется 8 раз |
| `Themes/UiTheme.xaml` | все токены в `ThemeDictionaries Dark` + `Light` (§3.2) + стили: `GlassCardStyle`, `DropZoneStyle`, `PillItemStyle`, `VbAccentButtonStyle`, `VbSecondaryButtonStyle`, `VbDangerButtonStyle` |
| `App.xaml` | merge `UiTheme.xaml`; **`RequestedTheme` не задаётся** (окно следует системной теме); переключателя темы нет (v0.1) |

Ассеты не нужны: только системные FontIcon (Segoe Fluent Icons), свой логотип при желании
— решение владельца, к спеке не привязано. Дубликатов виджетов/стилей не заводим.

---

## 7. Стандарты красоты — чек-лист для ui-dev

1. Ритм отступов: только 4/8/12/16/24 из токенов, ничего по вкусу (ана-боли D8).
2. На вьюпорте ≤ 1 фиолетового акцента (CTA); «Отмена» — danger, не второй акцент;
   голубой не используется в той же зоне, что и фиолетовый CTA.
3. No clipping: все подписи в `Segmented`/row-ствах живут в Grid-разметке с Margin=4 —
   никаких `Canvas.SetLeft`/координатной вёрстки (ана-боли D1).
4. Пустые состояния всегда осмысленно заполнены: drop-зона, список видео, журнал (не
   «мёртвые прямоугольники» — ана-боли D6/D7).
5. Слот прогресса зарезервирован: кольцо/%/шаг сидят в фиксированном Grid-ряду, ничего
   не сдвигается при появлении спиннера (ана-боли D5).
6. Ось меток: все row-метки — колонка `Width="96"` (единая ось ±1 px — ана-боли D2).
7. Мotion — только встроенный Fluent: fadeIn+slide 150 ms у карточек, штатный переход
   выбора в чипе, автопрогресс; ноль кастомных анимаций на слабом GPU.
8. `IsEnabled=False` визуально редуцирован (وضность), но читаем (текст ↔ Secondary).
9. Двухвариантные пилюли без «растянутой дыры»: ширина группы по контенту (ана-боли D4).
10. Контраст: текст ≥ 4.5:1, UI-элементы ≥ 3:1 — проверяется `a11y-auditor` **в ОБЕИХ темах**
    (Dark и Light).
11. ToggleSwitch/кнопки/пилюли — на одном наборе токенов; никаких двух разных
    вторичных стилей кнопок и двух разных карточек.

---

## 8. Заголовок окна (кастомный Titlebar)

- `ExtendsContentIntoTitleBar = true` + `SetTitleBar(AppTitleGrid)` (WindowsAppSDK 1.5):
  свой заголовок — просто нативная панель поверх Mica; слева `AppIcon` (20 px) + Title 20
  «VideoBoost» + Caption 12 подзаголовок; справа — **стандартные системные caption-кнопки**
  (никогда не переопределяем).
- Интерактивные элементы (кнопки, chip) в титлбаре не живём — они в `BottomStrip`;
  интерактив в зоне drag запрещён.
- При миграции на WindowsAppSDK 1.6+ можно переехать на `AppWindow.TitleBar` — не входит
  в обязательный объём v0.1.
- Фича «стекло в шапке» = Mica, а не рисование графиков/блесков (legacy canvas-шапка —
  самодельная вёрстка, в v3 не переносится).

---

## 9. Приёмка (критерии без двоения)

**(а) Фич-паритет 1:1**
- Список видео + drag&drop ✅ (`VideoDropTarget`+`VideoList`+`AddVideosButton`).
- Пресеты Быстро/Баланс/Максимально + описания ✅ (`PresetPills`+`PresetDescriptionText`
  и пересеты параметров при смене пресета).
- Масштаб x2/x3/x4/4Kавто/8Kавто ✅ (`ScalePills`); Модель Авто/Лёгкая/Тяжёлая ✅ (`ModelPills`);
  Плавность вкл/выкл + FPS 60/120 ✅ (`InterpSwitch`+`FpsPills`); Тип Обычное/Аниме ✅
  (`ContentPills`); Кодировщик Авто/H.264/H.265/CPU ✅ (`EncoderPills`); Качество
  Авто/Скорость/Баланс/Макс ✅ (`QualityPills`); Tile Авто/256/384/512 ✅ (`TilePills`);
  «Экономить место: JPEG» ✅ (`SaveSpaceSwitch`).
- Начать/Отмена/Открыть папку ✅; прогресс+проценты+текст шага ✅ (`BoostProgress`,
  `BoostPercentText`, `BoostStatusText`, `CurrentFileText`); «Удалить выбранное» ✅
  (`RemoveVideosButton`+`Delete`);
- Журнал внизу + «Очистить» ✅ (`JournalPanel`+`ClearLogButton`); футер: статус
  «Инструменты готовы/качаются» + кнопка скачивания ✅ (`ToolsStatusChip`
  +`PrepareToolsButton`); 11 legacy-тултипов ✅ (ToolTipService); ошибка видна в журнале ✅.
- Prefs `ui_settings.json`: `preset, scale, model, fps, encoder, quality, tile,
  interpolate, save_space, content, journal_open, geometry` — **без `advanced_expanded`**
  (исключён, дельта v3.1).

**(б) Высота SettingsCard и зоны сжатия (v3.1)**
- Было (Экспандер свернут) ≈ 380 px → стало **≈ 500–520 px** (рост ≈ +120).
- Правая колонка @960×784: доступно `784 − 44 − 12 − 36 − 12 ≈ 680` (журнал закрыт),
  при журнале открытом ≈ 522 → контент влезает; ScrollViewer активируется только при
  «окно 784 ∧ журнал открыт ∧ виден InfoBar 48 px».
- Порядок сжатия при дефиците высоты: 1) `VideoCard` (список до min 220–240),
  2) правый ScrollViewer; `RunCard`/`JournalPanel`/`BottomStrip`/`Titlebar` фиксированы.

**(в) Ничего не перекрывается ни при какой ширине 960..1440**
- Колонки 58/42 с MinWidth 520/336, вся схема на Grid-строках/колонках (никаких
  `Canvas`, no absolute positions); InfoBar reflow-ит тело (Row Auto), не перекрывает.

**(г) Все контролы — из готовых системных**
- `Segmented` (CommunityToolkit), `InfoBar`, `TeachingTip`, `ToggleSwitch`, `ListView`,
  `ProgressBar`/`ProgressRing`, `FontIcon` (Segoe Fluent Icons); ни одного `Canvas`/self-drawn.

**(д) Сборка без Visual Studio**
- `dotnet build VideoBoost.sln -p:Platform=x64` — зелёная, без предупреждений;
  publish `dotnet publish -c Release -r win-x64 --self-contained false` (профиль — решает
  владелец); новый NuGet: `CommunityToolkit.WinUI.Controls.Segmented` (разрешён по AGENTS.md).

**(е) Контрольная точка владельца**
- Скриншоты в 1100×900 и 960×784, проверка 4 состояний («Пусто», «Готов» (2 файла),
  «Обработка», «Ошибка») + **скриншот Light-темы 1100×900 (минимум: «Пусто», «Обработка»)**.

---

## 10. Ограничения движка (для engine-dev)

- GUI не блокируется: вся обработка через `async/await` + `CancellationToken` на каждый
  процесс FFmpeg/ESRGAN/RIFE/скачивание.
- Прогресс — `IProgress<T>` через `DispatcherQueue'; обновления UI — только в UI-потоке.
- Процессы — системные `Process`; kill по дереву `Process.Kill(entireProcessTree: true)`
  (эквивалент legacy «root-process + дети»).
- Очередь файлов в движке (не в UI): UI submit-рует модель `RunRequest` (файлы + настройки),
  дальше всё делает движок.
- Temp-файлы чистятся автоматически (после отмены и после каждой сессии); ошибка
  пользователя уходит в журнал/InfoBar — окно не падает.
- Пути только `Path.Combine` / `Environment.ProcessPath`; кириллица/пробелы — норма.

---

## 11. Решения владельца (зафиксированы)

| # | Вопрос | Решение |
|---|---|---|
| 1 | Журнал | Утверждено: авто-раскрытие при старте обработки и при ошибке; в остальное время закрыт, полоса 36 px всегда видна |
| 2 | Кастомный Titlebar | Утверждено: `ExtendsContentIntoTitleBar` + `SetTitleBar(AppTitleGrid)`, Mica-шапка (§8) |
| 3 | Сворачиваемые настройки (Expander) | **Изменение №1 v3.1**: убран — 8 строк всегда видны; группа «Кодирование и хранение» через `SettingsDivider2` + `EncodeGroupHeader` |
| 4 | Темы | **Изменение №2 v3.1**: Dark **и** Light через `ThemeDictionaries`; `RequestedTheme` не форсится; переключателя темы в UI нет (v0.1) |
| 5 | Default-пресет и 8K-предупреждение | Утверждено: default «Баланс»; `TeachingTip8K` при x4/«8K авто»/«Максимально» — оставить |

---

## История утверждений

| Дата | Версия | Событие |
|---|---|---|
| 07.11.2026 | v3.0 | Спека §0–§11 предложена ux-designer (обзор: legacy main.py/engine.py + docs/redesign-spec-v2.md; ответы на вопросы владельцу в §11). |
| 07.11.2026 | v3.1 (дельта) | Владелец утвердил спеку с двумя изменениями: (1) Expander «Продвинутые» убран — `SettingsCard`: 8 строк всегда видны + `SettingsDivider2`/`EncodeGroupHeader`; pref `advanced_expanded` исключён; `SpeedNoteText` сразу после `SaveSpaceSwitch`; подтверждена высота (~+120 px) и порядок сжатия; (2) темы Dark + Light — токены в `ThemeDictionaries` обоих словарей, `RequestedTheme` не форсится, без переключателя темы в v0.1; новые токены `VbAccentFillBrush/Hover/Pressed` (контраст White-on-accent: 4.35:1 → альтернативы приёмчатеми заливками); severity-цвета не перекрашиваются по темам — только Light-аналоги Success/Warning/Danger; приёмка дополнена Light-скриншотом. |
| 07.11.2026 | v3.1 (файл) | Дельты применены прямо в соответствующие разделы (§1.1, §1.3, §2, §3, §4, §6, §7, §9, §11); этот файл — единственная действующая редакция. |

*Конец. Спека v3.1 — полное ТЗ для `ui-dev`; вёрстка по ней, самовольные отклонения
(Expander, Dark-only, самодельные канвасы) запрещены.*
