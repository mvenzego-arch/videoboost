using System.Collections.Specialized;
using Microsoft.UI;
using Microsoft.UI.Composition.SystemBackdrops;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using VideoBoost.App.Services;
using Windows.Graphics;

namespace VideoBoost.App.Views;

/// <summary>
/// Главное окно VideoBoost v3.1: титлбар, InfoBar, тело 58/42, журнал и нижняя полоса.
/// Состояния переключаются RunCard/журналом; пайплайн движка подключается в iteration 2.
/// </summary>
public sealed partial class MainWindow : Window
{
    private const int DefaultWidth = 1100;
    private const int DefaultHeight = 900;

    private bool _journalOpen;

    /// <summary>Создаёт окно, настраивает Mica, титлбар и связи между карточками.</summary>
    public MainWindow()
    {
        InitializeComponent();

        Title = "VideoBoost — улучшение видео и плавности";
        ConfigureWindow();
        ConfigureBackdrop();

        ExtendsContentIntoTitleBar = true;
        SetTitleBar(AppTitleGrid);
        TeachingTip8K.Target = SettingsCardBody.PresetPillsAnchor;

        RunCardBody.StartRequested += RunCardBody_StartRequested;
        RunCardBody.CancelRequested += RunCardBody_CancelRequested;
        RunCardBody.OpenFolderRequested += RunCardBody_OpenFolderRequested;
        VideoCardBody.VideoCountChanged += VideoCardBody_VideoCountChanged;

        LogService.Instance.Entries.CollectionChanged += Entries_CollectionChanged;
        Closed += MainWindow_Closed;

        LogService.Instance.Info("VideoBoost запущен: добавьте видео и выберите пресет.");
    }

    private void ConfigureWindow()
    {
        try
        {
            AppWindow.Resize(new SizeInt32(DefaultWidth, DefaultHeight));
            AppWindow.Title = Title;
            AppWindow.SetIcon(Path.Combine(AppContext.BaseDirectory, "Assets", "video_boost.ico"));
        }
        catch (Exception ex)
        {
            // Окно уже открыто; отсутствие иконки/размера — не повод падать.
            LogService.Instance.Warning($"Не удалось настроить параметры окна: {ex.Message}");
        }
    }

    /// <summary>
    /// Mica BaseAlt в обеих темах; на слабых/старых системах остаётся сплошной
    /// <c>VbBackdropBrush</c> из XAML. Свой Acrylic не применяем (§3.1).
    /// </summary>
    private void ConfigureBackdrop()
    {
        try
        {
            if (MicaController.IsSupported())
            {
                SystemBackdrop = new MicaBackdrop { Kind = MicaKind.BaseAlt };
                RootGrid.Background = new SolidColorBrush(Colors.Transparent);
            }
            else
            {
                LogService.Instance.Info("Mica недоступна — используется сплошной фон темы.");
            }
        }
        catch (Exception ex)
        {
            LogService.Instance.Warning($"Mica не включена: {ex.Message}");
        }
    }

    private void SetJournalOpen(bool open)
    {
        _journalOpen = open;
        JournalPanelBody.Visibility = open ? Visibility.Visible : Visibility.Collapsed;
        JournalChevron.Glyph = open ? "\uE70D" : "\uE70E";
        ToolTipService.SetToolTip(JournalToggle, open ? "Свернуть журнал" : "Развернуть журнал");
    }

    private void ShowNotification(InfoBarSeverity severity, string title, string message)
    {
        NotificationBar.Severity = severity;
        NotificationBar.Title = title;
        NotificationBar.Message = message;
        NotificationBar.IsOpen = true;
    }

    private void Entries_CollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        ClearLogButton.IsEnabled = LogService.Instance.Entries.Count > 0;

        if (e.Action != NotifyCollectionChangedAction.Add || e.NewItems is null)
        {
            return;
        }

        // Ошибка: журнал раскрывается сам, краткая суть — в InfoBar (§4, состояние 6).
        foreach (object item in e.NewItems)
        {
            if (item is LogEntry { Level: LogLevel.Error } entry)
            {
                SetJournalOpen(true);
                ShowNotification(InfoBarSeverity.Error, "Ошибка", entry.Message);
                break;
            }
        }
    }

    private void VideoCardBody_VideoCountChanged(object? sender, int count)
    {
        RunCardBody.SetFileCount(count);

        // TODO(iteration 2): при count > 0 и готовых инструментах — RunCardBody.SetStartEnabled(true).
        if (count == 0)
        {
            RunCardBody.ResetProgress();
        }
    }

    private void RunCardBody_StartRequested(object? sender, EventArgs e)
    {
        // TODO(iteration 2): собрать RunRequest (файлы + настройки) и отдать в IEngineService.
        LogService.Instance.Info("Запуск обработки: пайплайн движка подключается в iteration 2.");
        SetJournalOpen(true);
    }

    private void RunCardBody_CancelRequested(object? sender, EventArgs e)
    {
        // TODO(iteration 2): CancellationToken → IEngineService.CancelAsync.
        LogService.Instance.Info("Отмена обработки: движок подключается в iteration 2.");
    }

    private void RunCardBody_OpenFolderRequested(object? sender, EventArgs e)
    {
        // TODO(iteration 2): открыть папку output после успешной обработки.
        LogService.Instance.Info("«Открыть папку» станет доступна после первой обработки.");
    }

    private void JournalToggle_Click(object sender, RoutedEventArgs e) => SetJournalOpen(!_journalOpen);

    private void ClearLogButton_Click(object sender, RoutedEventArgs e) => LogService.Instance.Clear();

    private void PrepareToolsButton_Click(object sender, RoutedEventArgs e)
    {
        // TODO(iteration 2): скачивание Real-ESRGAN/RIFE с прогрессом в InfoBar.
        LogService.Instance.Info("Скачивание инструментов появится в следующей итерации.");
    }

    private void StartAccelerator_Invoked(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args) =>
        args.Handled = RunCardBody.RaiseStartIfEnabled();

    private void CancelAccelerator_Invoked(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args) =>
        args.Handled = RunCardBody.RaiseCancelIfEnabled();

    private void MainWindow_Closed(object sender, WindowEventArgs args)
    {
        LogService.Instance.Entries.CollectionChanged -= Entries_CollectionChanged;
        RunCardBody.StartRequested -= RunCardBody_StartRequested;
        RunCardBody.CancelRequested -= RunCardBody_CancelRequested;
        RunCardBody.OpenFolderRequested -= RunCardBody_OpenFolderRequested;
        VideoCardBody.VideoCountChanged -= VideoCardBody_VideoCountChanged;
    }
}
