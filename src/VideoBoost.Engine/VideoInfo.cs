namespace VideoBoost.Engine;

/// <summary>
/// Данные о видео, полученные от ffprobe. В v3 это чистый DTO без файлового IO:
/// заполнение выполняет слой probe (следующий шаг движка).
/// </summary>
/// <param name="Path">Полный путь к исходному видео (кириллица и пробелы допустимы).</param>
/// <param name="Width">Ширина кадра в пикселях.</param>
/// <param name="Height">Высота кадра в пикселях.</param>
/// <param name="Fps">Средняя частота кадров исходника.</param>
/// <param name="Duration">Длительность в секундах.</param>
/// <param name="AudioCodec">Имя аудиокодека ffprobe (например, <c>aac</c>) или <see langword="null"/>.</param>
/// <param name="IsHdr">Признак HDR (PQ/HLG): пайплайн кадров переводит его в SDR 8 бит.</param>
/// <param name="FramesHint">Подсказка о числе кадров из ffprobe; 0 — неизвестно.</param>
public sealed record VideoInfo(
    string Path,
    int Width,
    int Height,
    double Fps,
    double Duration,
    string? AudioCodec,
    bool IsHdr,
    int FramesHint = 0)
{
    /// <summary>Есть ли в исходнике аудиодорожка.</summary>
    public bool HasAudio => !string.IsNullOrEmpty(AudioCodec);

    /// <summary>Количество пикселей одного кадра.</summary>
    public long PixelCount => (long)Width * Height;
}
