namespace VideoBoost.Engine.Processes;

/// <summary>
/// Результат завершённого нативного процесса: код возврата, захваченные потоки и
/// длительность. Отмена и ошибки запуска выбрасываются исключениями, поэтому сюда
/// попадают только процессы, которые действительно завершились.
/// </summary>
/// <param name="ExitCode">Код возврата процесса (0 — успех).</param>
/// <param name="StandardOutput">Захваченный stdout; при переполнении помечается как усечённый.</param>
/// <param name="StandardError">Захваченный stderr; при переполнении помечается как усечённый.</param>
/// <param name="Duration">Время от запуска до завершения процесса.</param>
public sealed record ProcessResult(
    int ExitCode,
    string StandardOutput,
    string StandardError,
    TimeSpan Duration)
{
    /// <summary>Процесс завершился успешно (<see cref="ExitCode"/> равен 0).</summary>
    public bool Succeeded => ExitCode == 0;

    /// <summary>
    /// Возвращает последние непустые строки stderr (или stdout, если stderr пуст) —
    /// то, что legacy писала в журнал как причину ошибки.
    /// </summary>
    /// <param name="maxLines">Сколько последних строк вернуть; должно быть положительным.</param>
    /// <returns>Строки через перевод строки окружения или пустая строка.</returns>
    public string ErrorTail(int maxLines = 30)
    {
        if (maxLines <= 0)
        {
            return string.Empty;
        }

        var source = string.IsNullOrWhiteSpace(StandardError) ? StandardOutput : StandardError;
        if (string.IsNullOrWhiteSpace(source))
        {
            return string.Empty;
        }

        var lines = source
            .Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.TrimEnd('\r'))
            .Where(line => !string.IsNullOrWhiteSpace(line))
            .ToArray();

        if (lines.Length == 0)
        {
            return string.Empty;
        }

        var tail = lines.Length <= maxLines ? lines : lines[^maxLines..];
        return string.Join(Environment.NewLine, tail);
    }

    /// <summary>
    /// Проверяет код возврата и при ошибке бросает <see cref="ProcessExecutionException"/>
    /// с хвостом вывода — удобно для стадий пайплайна.
    /// </summary>
    /// <param name="operation">Название операции для сообщения («Извлечение кадров» и т. п.).</param>
    /// <returns>Этот же результат, если процесс завершился успешно.</returns>
    /// <exception cref="ProcessExecutionException">Код возврата не равен 0.</exception>
    public ProcessResult EnsureSuccess(string operation)
    {
        if (Succeeded)
        {
            return this;
        }

        var tail = ErrorTail();
        var message = string.IsNullOrEmpty(tail)
            ? $"{operation}: процесс завершился с кодом {ExitCode}."
            : $"{operation}: процесс завершился с кодом {ExitCode}.{Environment.NewLine}{tail}";

        throw new ProcessExecutionException(message, this);
    }
}

/// <summary>
/// Ошибка запуска или ненулевого завершения нативного процесса. Содержит снимок
/// <see cref="Result"/> (если процесс успел завершиться), чтобы пайплайн мог показать
/// пользователю хвост stderr.
/// </summary>
public sealed class ProcessExecutionException : Exception
{
    /// <summary>Создаёт исключение с результатом завершённого процесса.</summary>
    /// <param name="message">Сообщение для журнала.</param>
    /// <param name="result">Результат процесса.</param>
    public ProcessExecutionException(string message, ProcessResult result)
        : base(message)
    {
        Result = result;
    }

    /// <summary>Создаёт исключение ошибки запуска процесса без результата.</summary>
    /// <param name="message">Сообщение для журнала.</param>
    /// <param name="innerException">Исходная ошибка (например, <c>Win32Exception</c>).</param>
    public ProcessExecutionException(string message, Exception innerException)
        : base(message, innerException)
    {
    }

    /// <summary>Результат процесса или <see langword="null"/>, если запуск не состоялся.</summary>
    public ProcessResult? Result { get; }

    /// <summary>Код возврата процесса или <see langword="null"/>, если запуск не состоялся.</summary>
    public int? ExitCode => Result?.ExitCode;

    /// <summary>Хвост stderr завершившегося процесса (см. <see cref="ProcessResult.ErrorTail"/>).</summary>
    /// <param name="maxLines">Сколько последних строк вернуть.</param>
    /// <returns>Строки ошибки или пустая строка.</returns>
    public string ErrorTail(int maxLines = 30) => Result?.ErrorTail(maxLines) ?? string.Empty;
}
