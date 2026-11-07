using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace VideoBoost.App.Views.Controls;

/// <summary>
/// Карточка запуска: «Начать / Отмена / Открыть папку», зарезервированный ряд прогресса
/// (кольцо + полоса + %) и строка «шаг / файл N из M». Состояния переключает MainWindow.
/// </summary>
public sealed partial class RunCard : UserControl
{
    private bool _running;
    private bool _startEnabled;

    /// <summary>Создаёт карточку запуска в состоянии «Пусто».</summary>
    public RunCard()
    {
        InitializeComponent();
        SetFileCount(0);
        UpdateStartButton();
    }

    /// <summary>Пользователь нажал «Начать обработку» (кнопка или Enter).</summary>
    public event EventHandler? StartRequested;

    /// <summary>Пользователь нажал «Отмена» (кнопка или Escape).</summary>
    public event EventHandler? CancelRequested;

    /// <summary>Пользователь нажал «Открыть папку».</summary>
    public event EventHandler? OpenFolderRequested;

    /// <summary>Разрешает или запрещает запуск (состояние «Готов»/«Пусто»).</summary>
    /// <param name="enabled">True — кнопка «Начать» доступна, если обработка не идёт.</param>
    public void SetStartEnabled(bool enabled)
    {
        _startEnabled = enabled;
        UpdateStartButton();
    }

    /// <summary>Обновляет подпись кнопки: «▶ Начать обработку (N)» при N &gt; 1.</summary>
    /// <param name="count">Количество выбранных видео.</param>
    public void SetFileCount(int count)
    {
        StartButton.Content = count > 1
            ? $"▶  Начать обработку ({count})"
            : "▶  Начать обработку";
    }

    /// <summary>
    /// Переключает состояние «Обработка»: «Начать» прячется прозрачностью (слот не прыгает),
    /// «Отмена» становится доступной, кольцо прогресса крутится.
    /// </summary>
    /// <param name="running">True — идёт обработка.</param>
    public void SetRunning(bool running)
    {
        _running = running;
        UpdateStartButton();
        CancelButton.IsEnabled = running;
        BoostRing.IsActive = running;
    }

    /// <summary>Обновляет прогресс, шаг и счётчик файлов.</summary>
    /// <param name="percent">Прогресс 0–100.</param>
    /// <param name="statusText">Текст шага («Апскейл 37%»); null — не менять.</param>
    /// <param name="currentFileText">«Файл 2 из 5»; null — не менять.</param>
    public void UpdateProgress(double percent, string? statusText = null, string? currentFileText = null)
    {
        double value = Math.Clamp(percent, 0, 100);
        BoostProgress.Value = value;
        BoostPercentText.Text = $"{Math.Round(value)}%";

        if (statusText is not null)
        {
            BoostStatusText.Text = statusText;
        }

        if (currentFileText is not null)
        {
            CurrentFileText.Text = currentFileText;
        }
    }

    /// <summary>Возвращает карточку в состояние «Готов к работе» (прогресс сброшен).</summary>
    public void ResetProgress()
    {
        BoostProgress.Value = 0;
        BoostPercentText.Text = "0%";
        BoostStatusText.Text = "Готов к работе";
        CurrentFileText.Text = string.Empty;
    }

    /// <summary>Запускает обработку по Enter, если кнопка доступна.</summary>
    /// <returns>True — событие отправлено (ускоритель можно считать обработанным).</returns>
    public bool RaiseStartIfEnabled()
    {
        if (!StartButton.IsEnabled || _running)
        {
            return false;
        }

        StartRequested?.Invoke(this, EventArgs.Empty);
        return true;
    }

    /// <summary>Отменяет обработку по Escape, если кнопка доступна.</summary>
    /// <returns>True — событие отправлено.</returns>
    public bool RaiseCancelIfEnabled()
    {
        if (!CancelButton.IsEnabled)
        {
            return false;
        }

        CancelRequested?.Invoke(this, EventArgs.Empty);
        return true;
    }

    private void UpdateStartButton()
    {
        StartButton.IsEnabled = _startEnabled && !_running;
        StartButton.Opacity = _running ? 0 : 1;
        StartButton.IsHitTestVisible = !_running;
        StartButton.IsTabStop = !_running;
    }

    private void StartButton_Click(object sender, RoutedEventArgs e) =>
        StartRequested?.Invoke(this, EventArgs.Empty);

    private void CancelButton_Click(object sender, RoutedEventArgs e) =>
        CancelRequested?.Invoke(this, EventArgs.Empty);

    private void OpenFolderButton_Click(object sender, RoutedEventArgs e) =>
        OpenFolderRequested?.Invoke(this, EventArgs.Empty);
}
