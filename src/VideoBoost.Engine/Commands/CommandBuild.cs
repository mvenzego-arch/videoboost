using System.Globalization;
using System.Text;

namespace VideoBoost.Engine.Commands;

/// <summary>
/// Готовая к запуску команда нативного инструмента: исполняемый файл, список
/// аргументов (без строковой склейки) и рабочий каталог. Строители команд
/// возвращают этот объект; запуск выполняет <see cref="Processes.IProcessRunner"/>.
/// </summary>
/// <param name="FileName">Полный путь к исполняемому файлу.</param>
/// <param name="Arguments">Аргументы в порядке передачи; каждый элемент — отдельный argv.</param>
/// <param name="WorkingDirectory">Рабочий каталог процесса или <see langword="null"/>.</param>
public sealed record NativeCommand(
    string FileName,
    IReadOnlyList<string> Arguments,
    string? WorkingDirectory = null)
{
    /// <summary>
    /// Строка команды только для журнала и dry-run. Для запуска не используется:
    /// аргументы передаются через <c>ProcessStartInfo.ArgumentList</c>.
    /// </summary>
    /// <returns>Читаемое представление команды с кавычками для аргументов с пробелами.</returns>
    public string ToLogString() => CommandBuild.FormatForLog(FileName, Arguments);

    /// <inheritdoc />
    public override string ToString() => ToLogString();
}

/// <summary>
/// Общие операции построителей команд: отладочное представление и инвариантное
/// форматирование чисел для аргументов FFmpeg/Real-ESRGAN/RIFE.
/// </summary>
public static class CommandBuild
{
    private static readonly char[] QuotingChars = [' ', '\t', '\n', '\r', '"'];

    /// <summary>Форматирует команду для журнала, заключая аргументы с пробелами в кавычки.</summary>
    /// <param name="fileName">Исполняемый файл.</param>
    /// <param name="arguments">Список аргументов.</param>
    /// <returns>Читаемая строка команды (не для передачи в Process).</returns>
    /// <exception cref="ArgumentException">Путь к исполняемому файлу пуст.</exception>
    public static string FormatForLog(string fileName, IReadOnlyList<string> arguments)
    {
        if (string.IsNullOrWhiteSpace(fileName))
        {
            throw new ArgumentException("Путь к исполняемому файлу не задан.", nameof(fileName));
        }

        ArgumentNullException.ThrowIfNull(arguments);

        var builder = new StringBuilder();
        builder.Append(Quote(fileName));
        foreach (var argument in arguments)
        {
            builder.Append(' ');
            builder.Append(Quote(argument));
        }

        return builder.ToString();
    }

    /// <summary>Форматирует команду для журнала.</summary>
    /// <param name="command">Команда нативного инструмента.</param>
    /// <returns>Читаемая строка команды (не для передачи в Process).</returns>
    public static string FormatForLog(NativeCommand command)
    {
        ArgumentNullException.ThrowIfNull(command);
        return FormatForLog(command.FileName, command.Arguments);
    }

    /// <summary>Целое число в инвариантной культуре — для аргументов процессов.</summary>
    /// <param name="value">Значение.</param>
    /// <returns>Строковое представление без региональных различий.</returns>
    public static string Invariant(int value) => value.ToString(CultureInfo.InvariantCulture);

    /// <summary>Число с плавающей точкой в инвариантной культуре — для аргументов процессов.</summary>
    /// <param name="value">Значение.</param>
    /// <param name="format">Строка формата .NET; по умолчанию до шести знаков после точки.</param>
    /// <returns>Строковое представление без региональных различий.</returns>
    public static string Invariant(double value, string format = "0.######") =>
        value.ToString(format, CultureInfo.InvariantCulture);

    /// <summary>
    /// Заключает аргумент в кавычки по правилам Windows только для отображения
    /// в журнале. В Process аргументы уходят через <c>ArgumentList</c>.
    /// </summary>
    internal static string Quote(string value)
    {
        if (value.Length == 0)
        {
            return "\"\"";
        }

        if (value.IndexOfAny(QuotingChars) < 0)
        {
            return value;
        }

        var builder = new StringBuilder(value.Length + 8);
        builder.Append('"');
        var backslashes = 0;
        foreach (var character in value)
        {
            if (character == '\\')
            {
                backslashes++;
                continue;
            }

            if (character == '"')
            {
                builder.Append('\\', (backslashes * 2) + 1);
                builder.Append('"');
                backslashes = 0;
                continue;
            }

            if (backslashes > 0)
            {
                builder.Append('\\', backslashes);
                backslashes = 0;
            }

            builder.Append(character);
        }

        if (backslashes > 0)
        {
            builder.Append('\\', backslashes * 2);
        }

        builder.Append('"');
        return builder.ToString();
    }
}
