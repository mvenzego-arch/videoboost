using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VideoBoost.App.Services;

namespace VideoBoost.App;

/// <summary>
/// Точка входа приложения. Ничего, кроме запуска главного окна: вся логика — в Views/Services.
/// </summary>
public partial class App : Application
{
    private static Window? _fallbackWindow;

    /// <summary>Создаёт приложение и подписывается на глобальный перехват ошибок.</summary>
    public App()
    {
        InitializeComponent();
        _ = LogService.Instance; // фиксируем UI-поток для журнала до создания окон
        UnhandledException += OnUnhandledException;
    }

    /// <summary>Главное окно (нужно пикерам файлов для инициализации HWND).</summary>
    public static Window? MainWindowInstance { get; private set; }

    /// <inheritdoc />
    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        try
        {
            MainWindowInstance = new Views.MainWindow();
            MainWindowInstance.Activate();
        }
        catch (Exception ex)
        {
            LogService.Instance.Error($"Не удалось открыть главное окно: {ex.Message}");
            ShowFallbackWindow(ex);
        }
    }

    private void OnUnhandledException(object sender, Microsoft.UI.Xaml.UnhandledExceptionEventArgs e)
    {
        LogService.Instance.Error($"Неперехваченная ошибка: {e.Exception?.Message ?? e.Message}");
        e.Handled = true;
    }

    private static void ShowFallbackWindow(Exception ex)
    {
        _fallbackWindow = new Window { Title = "VideoBoost — ошибка запуска" };
        _fallbackWindow.Content = new TextBlock
        {
            Text = "Не удалось загрузить интерфейс VideoBoost.\n\n" + ex.Message,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(24),
        };
        _fallbackWindow.Activate();
    }
}
