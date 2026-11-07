namespace VideoBoost.Engine.Commands;

/// <summary>
/// Построитель команды интерполяции кадров RIFE ncnn Vulkan. Аргументы перенесены
/// из legacy <c>process_video</c>: <c>-i/-o/-n/-m/-g/-j/-f</c> и флаг <c>-u</c>
/// для повторной попытки в UHD-режиме.
/// </summary>
public static class InterpCommands
{
    /// <summary>
    /// Строит команду интерполяции каталога кадров до нужного числа кадров.
    /// </summary>
    /// <param name="rifePath">Путь к <c>rife-ncnn-vulkan.exe</c>.</param>
    /// <param name="inputDirectory">Каталог кадров после апскейла.</param>
    /// <param name="outputDirectory">Каталог кадров после интерполяции (должен существовать).</param>
    /// <param name="targetFrameCount">Желаемое число кадров для <c>-n</c>.</param>
    /// <param name="modelDirectory">Каталог модели <c>-m</c> (например, <c>rife-v4.6</c>).</param>
    /// <param name="format">Формат кадров для <c>-f</c>.</param>
    /// <param name="uhdMode">Добавить <c>-u</c> (UHD-режим, меньше видеопамяти).</param>
    /// <returns>Команда с рабочим каталогом рядом с исполняемым файлом (как в legacy).</returns>
    public static NativeCommand BuildInterpolateCommand(
        string rifePath,
        string inputDirectory,
        string outputDirectory,
        int targetFrameCount,
        string modelDirectory,
        FrameImageFormat format,
        bool uhdMode = false)
    {
        if (string.IsNullOrWhiteSpace(rifePath))
        {
            throw new ArgumentException("Путь к RIFE не задан.", nameof(rifePath));
        }

        if (string.IsNullOrWhiteSpace(inputDirectory))
        {
            throw new ArgumentException("Каталог входных кадров не задан.", nameof(inputDirectory));
        }

        if (string.IsNullOrWhiteSpace(outputDirectory))
        {
            throw new ArgumentException("Каталог выходных кадров не задан.", nameof(outputDirectory));
        }

        if (targetFrameCount <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(targetFrameCount),
                targetFrameCount,
                "Целевое число кадров должно быть положительным.");
        }

        if (string.IsNullOrWhiteSpace(modelDirectory))
        {
            throw new ArgumentException("Каталог модели не задан.", nameof(modelDirectory));
        }

        var arguments = new List<string>
        {
            "-i", inputDirectory,
            "-o", outputDirectory,
            "-n", CommandBuild.Invariant(targetFrameCount),
            "-m", modelDirectory,
            "-g", "0",
            "-j", "1:1:1",
            "-f", format.InterpolatedFilePattern(),
        };

        if (uhdMode)
        {
            arguments.Add("-u");
        }

        return new NativeCommand(rifePath, arguments, Path.GetDirectoryName(rifePath));
    }

    /// <summary>
    /// Целевое число кадров после интерполяции: <c>max(2, round(duration × targetFps))</c>,
    /// как в legacy (Python <c>round</c> — банковское округление, .NET по умолчанию тоже).
    /// </summary>
    /// <param name="durationSeconds">Длительность видео в секундах.</param>
    /// <param name="targetFps">Целевая частота (60 или 120).</param>
    /// <returns>Число кадров не меньше 2.</returns>
    public static int ComputeTargetFrameCount(double durationSeconds, int targetFps)
    {
        if (durationSeconds <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(durationSeconds),
                durationSeconds,
                "Длительность должна быть положительной.");
        }

        if (targetFps <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(targetFps), targetFps, "FPS должен быть положительным.");
        }

        return Math.Max(2, (int)Math.Round(durationSeconds * targetFps));
    }

    /// <summary>
    /// Нужна ли интерполяция: фактический FPS заметно ниже целевого и целевое число
    /// кадров больше исходного — точная копия условия legacy.
    /// </summary>
    /// <param name="effectiveFps">Фактический FPS исходного набора кадров.</param>
    /// <param name="targetFps">Целевая частота.</param>
    /// <param name="sourceFrameCount">Сколько кадров есть сейчас.</param>
    /// <param name="targetFrameCount">Сколько кадров нужно после интерполяции.</param>
    /// <returns><see langword="true"/>, если RIFE следует запускать.</returns>
    public static bool ShouldInterpolate(
        double effectiveFps,
        int targetFps,
        int sourceFrameCount,
        int targetFrameCount) =>
        effectiveFps < targetFps * 0.95 && targetFrameCount > sourceFrameCount + 1;
}
