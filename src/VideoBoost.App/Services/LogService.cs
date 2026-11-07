using System.Collections.ObjectModel;
using Microsoft.UI.Dispatching;

namespace VideoBoost.App.Services;

/// <summary>Уровень сообщения встроенного журнала.</summary>
public enum LogLevel
{
    /// <summary>Обычное информационное сообщение.</summary>
    Info,

    /// <summary>Предупреждение: часть данных пропущена, но работа продолжается.</summary>
    Warning,

    /// <summary>Ошибка: операция не выполнена, подробности — в сообщении.</summary>
    Error,
}

/// <summary>Одна строка журнала.</summary>
public sealed class LogEntry
{
    /// <summary>Создаёт строку журнала.</summary>
    public LogEntry(DateTimeOffset time, LogLevel level, string message)
    {
        Time = time;
        Level = level;
        Message = message;
    }

    /// <summary>Момент появления сообщения.</summary>
    public DateTimeOffset Time { get; }

    /// <summary>Уровень сообщения.</summary>
    public LogLevel Level { get; }

    /// <summary>Текст сообщения без времени.</summary>
    public string Message { get; }

    /// <summary>Готовая строка вида «12:34:56  текст».</summary>
    public string DisplayText => $"{Time:HH:mm:ss}  {Message}";
}

/// <summary>
/// Встроенный журнал приложения. Потокобезопасен: из фоновых потоков сообщение
/// маршалится в UI-поток через <see cref="DispatcherQueue.TryEnqueue"/>.
/// </summary>
public sealed class LogService
{
    private const int MaxEntries = 500;
    private readonly DispatcherQueue? _dispatcher = DispatcherQueue.GetForCurrentThread();

    /// <summary>Единственный экземпляр журнала на приложение.</summary>
    public static LogService Instance { get; } = new();

    /// <summary>Строки журнала для привязки к панели.</summary>
    public ObservableCollection<LogEntry> Entries { get; } = [];

    /// <summary>Добавляет информационное сообщение.</summary>
    public void Info(string message) => Write(LogLevel.Info, message);

    /// <summary>Добавляет предупреждение.</summary>
    public void Warning(string message) => Write(LogLevel.Warning, message);

    /// <summary>Добавляет сообщение об ошибке.</summary>
    public void Error(string message) => Write(LogLevel.Error, message);

    /// <summary>Очищает журнал (в UI-потоке).</summary>
    public void Clear()
    {
        if (_dispatcher is null || _dispatcher.HasThreadAccess)
        {
            Entries.Clear();
        }
        else
        {
            _dispatcher.TryEnqueue(Entries.Clear);
        }
    }

    private void Write(LogLevel level, string message)
    {
        if (string.IsNullOrWhiteSpace(message))
        {
            return;
        }

        LogEntry entry = new(DateTimeOffset.Now, level, message.Trim());
        if (_dispatcher is null || _dispatcher.HasThreadAccess)
        {
            Append(entry);
        }
        else
        {
            _dispatcher.TryEnqueue(() => Append(entry));
        }
    }

    private void Append(LogEntry entry)
    {
        Entries.Add(entry);
        while (Entries.Count > MaxEntries)
        {
            Entries.RemoveAt(0);
        }
    }
}
