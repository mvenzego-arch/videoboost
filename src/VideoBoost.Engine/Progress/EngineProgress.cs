namespace VideoBoost.Engine;

/// <summary>
/// Фазы конвейера обработки, о которых движок сообщает через <see cref="EngineProgress"/>.
/// Порядок значений соответствует ходу пайплайна legacy <c>process_video</c>.
/// </summary>
public enum EnginePhase
{
    /// <summary>Анализ исходника через ffprobe.</summary>
    Analyze,

    /// <summary>Извлечение кадров через FFmpeg.</summary>
    Extract,

    /// <summary>Нейросетевой апскейл через Real-ESRGAN.</summary>
    Upscale,

    /// <summary>Интерполяция кадров через RIFE.</summary>
    Interpolate,

    /// <summary>Сборка и кодирование результата через FFmpeg.</summary>
    Encode,

    /// <summary>Работа завершена успешно.</summary>
    Done,

    /// <summary>Работа отменена пользователем.</summary>
    Cancelled,

    /// <summary>Работа завершилась ошибкой.</summary>
    Failed,
}

/// <summary>
/// Единое сообщение о прогрессе движка для UI и журнала. <see cref="Percent"/> — доля
/// текущей фазы в диапазоне 0–100 (UI показывает её как есть), <see cref="Message"/> —
/// готовая строка для журнала, <see cref="FileIndex"/>/<see cref="FilesTotal"/> — позиция
/// файла в очереди (нумерация с 1; 0/0 — вне очереди).
/// </summary>
/// <param name="Phase">Текущая фаза конвейера.</param>
/// <param name="Percent">Прогресс фазы в процентах (0–100).</param>
/// <param name="Message">Необязательная строка для журнала.</param>
/// <param name="FileIndex">Номер текущего файла (с 1) или 0.</param>
/// <param name="FilesTotal">Всего файлов в очереди или 0.</param>
public sealed record EngineProgress(
    EnginePhase Phase,
    double Percent,
    string? Message = null,
    int FileIndex = 0,
    int FilesTotal = 0)
{
    /// <summary>Процент, приведённый к диапазону 0–100 (для UI и логов).</summary>
    public double ClampedPercent => Math.Clamp(Percent, 0d, 100d);

    /// <summary>Создаёт сообщение об успешном завершении.</summary>
    /// <param name="message">Необязательная строка для журнала.</param>
    /// <param name="fileIndex">Номер текущего файла (с 1) или 0.</param>
    /// <param name="filesTotal">Всего файлов в очереди или 0.</param>
    /// <returns>Сообщение фазы <see cref="EnginePhase.Done"/> со 100 %.</returns>
    public static EngineProgress Done(string? message = null, int fileIndex = 0, int filesTotal = 0) =>
        new(EnginePhase.Done, 100d, message, fileIndex, filesTotal);

    /// <summary>Создаёт сообщение об отмене.</summary>
    /// <param name="message">Необязательная строка для журнала.</param>
    /// <param name="fileIndex">Номер текущего файла (с 1) или 0.</param>
    /// <param name="filesTotal">Всего файлов в очереди или 0.</param>
    /// <returns>Сообщение фазы <see cref="EnginePhase.Cancelled"/>.</returns>
    public static EngineProgress Cancelled(string? message = null, int fileIndex = 0, int filesTotal = 0) =>
        new(EnginePhase.Cancelled, 0d, message, fileIndex, filesTotal);

    /// <summary>Создаёт сообщение об ошибке.</summary>
    /// <param name="message">Текст ошибки для журнала.</param>
    /// <param name="fileIndex">Номер текущего файла (с 1) или 0.</param>
    /// <param name="filesTotal">Всего файлов в очереди или 0.</param>
    /// <returns>Сообщение фазы <see cref="EnginePhase.Failed"/>.</returns>
    public static EngineProgress Failed(string message, int fileIndex = 0, int filesTotal = 0) =>
        new(EnginePhase.Failed, 0d, message, fileIndex, filesTotal);

    /// <summary>Возвращает копию сообщения с привязкой к файлу очереди.</summary>
    /// <param name="fileIndex">Номер текущего файла (с 1).</param>
    /// <param name="filesTotal">Всего файлов в очереди.</param>
    /// <returns>Копия сообщения с заполненными <see cref="FileIndex"/> и <see cref="FilesTotal"/>.</returns>
    public EngineProgress WithFile(int fileIndex, int filesTotal) =>
        this with { FileIndex = fileIndex, FilesTotal = filesTotal };
}
