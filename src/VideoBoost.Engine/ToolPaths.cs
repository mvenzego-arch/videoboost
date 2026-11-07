namespace VideoBoost.Engine;

/// <summary>Пути к нативным инструментам в tools\. Проверяются до старта пайплайна.</summary>
public sealed record ToolPaths(
    string FFmpeg,
    string FFprobe,
    string Realesrgan,
    string RealesrganModelsDir,
    string Rife,
    string RifeModel);
