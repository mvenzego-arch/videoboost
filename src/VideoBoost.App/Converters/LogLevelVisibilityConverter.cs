using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Data;
using VideoBoost.App.Services;

namespace VideoBoost.App.Converters;

/// <summary>
/// Показывает только тот TextBlock журнала, который соответствует уровню строки.
/// Цвет задаётся стилем с ThemeResource — конвертер не знает про палитру.
/// </summary>
public sealed class LogLevelVisibilityConverter : IValueConverter
{
    /// <inheritdoc />
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        LogLevel level = value is LogLevel entryLevel ? entryLevel : LogLevel.Info;
        string expected = parameter as string ?? nameof(LogLevel.Info);

        return string.Equals(level.ToString(), expected, StringComparison.OrdinalIgnoreCase)
            ? Visibility.Visible
            : Visibility.Collapsed;
    }

    /// <inheritdoc />
    public object ConvertBack(object value, Type targetType, object parameter, string language) =>
        throw new NotSupportedException("Обратное преобразование уровня журнала не требуется.");
}
