namespace VideoBoost.Engine.Commands;

/// <summary>
/// Построитель команды нейросетевого апскейла Real-ESRGAN ncnn Vulkan. Аргументы
/// перенесены из legacy <c>process_video</c> без изменений: <c>-i/-o/-s/-n/-m/-t/-g/-j/-f</c>.
/// </summary>
public static class UpscaleCommands
{
    private static readonly int[] FallbackTiles = [384, 256, 192, 128];

    /// <summary>
    /// Строит команду апскейла каталога кадров.
    /// </summary>
    /// <param name="realEsrganPath">Путь к <c>realesrgan-ncnn-vulkan.exe</c>.</param>
    /// <param name="inputDirectory">Каталог исходных кадров.</param>
    /// <param name="outputDirectory">Каталог увеличенных кадров (должен существовать).</param>
    /// <param name="scale">Множитель 2–4.</param>
    /// <param name="modelName">Имя модели ncnn для <c>-n</c> (см. <see cref="ModelNames"/>).</param>
    /// <param name="modelsDirectory">Каталог моделей <c>-m</c>.</param>
    /// <param name="tile">Размер tile <c>-t</c>.</param>
    /// <param name="format">Формат кадров для <c>-f</c>.</param>
    /// <returns>Команда с рабочим каталогом рядом с исполняемым файлом (как в legacy).</returns>
    public static NativeCommand BuildUpscaleCommand(
        string realEsrganPath,
        string inputDirectory,
        string outputDirectory,
        int scale,
        string modelName,
        string modelsDirectory,
        int tile,
        FrameImageFormat format)
    {
        if (string.IsNullOrWhiteSpace(realEsrganPath))
        {
            throw new ArgumentException("Путь к Real-ESRGAN не задан.", nameof(realEsrganPath));
        }

        if (string.IsNullOrWhiteSpace(inputDirectory))
        {
            throw new ArgumentException("Каталог входных кадров не задан.", nameof(inputDirectory));
        }

        if (string.IsNullOrWhiteSpace(outputDirectory))
        {
            throw new ArgumentException("Каталог выходных кадров не задан.", nameof(outputDirectory));
        }

        if (scale is < 1 or > 4)
        {
            throw new ArgumentOutOfRangeException(nameof(scale), scale, "Масштаб должен быть от 1 до 4.");
        }

        if (string.IsNullOrWhiteSpace(modelName))
        {
            throw new ArgumentException("Имя модели не задано.", nameof(modelName));
        }

        if (string.IsNullOrWhiteSpace(modelsDirectory))
        {
            throw new ArgumentException("Каталог моделей не задан.", nameof(modelsDirectory));
        }

        if (tile <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(tile), tile, "Tile должен быть положительным.");
        }

        var arguments = new List<string>
        {
            "-i", inputDirectory,
            "-o", outputDirectory,
            "-s", CommandBuild.Invariant(scale),
            "-n", modelName,
            "-m", modelsDirectory,
            "-t", CommandBuild.Invariant(tile),
            "-g", "0",
            "-j", "1:1:1",
            "-f", format.Extension(),
        };

        return new NativeCommand(realEsrganPath, arguments, Path.GetDirectoryName(realEsrganPath));
    }

    /// <summary>
    /// Список tile для повторных попыток при нехватке видеопамяти: исходный tile,
    /// затем 384/256/192/128 строго меньше исходного — как в legacy <c>process_video</c>.
    /// </summary>
    /// <param name="tile">Исходный tile.</param>
    /// <returns>Последовательность попыток (первая — исходный tile).</returns>
    public static IReadOnlyList<int> GetTileFallbacks(int tile)
    {
        if (tile <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(tile), tile, "Tile должен быть положительным.");
        }

        var tiles = new List<int> { tile };
        foreach (var fallback in FallbackTiles)
        {
            if (fallback < tile)
            {
                tiles.Add(fallback);
            }
        }

        return tiles;
    }
}
