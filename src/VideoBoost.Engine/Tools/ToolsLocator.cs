using System.Diagnostics;

namespace VideoBoost.Engine.Tools;

/// <summary>Вид нативного инструмента, который ищет движок.</summary>
public enum ToolKind
{
    /// <summary>FFmpeg — извлечение кадров и кодирование.</summary>
    Ffmpeg,

    /// <summary>ffprobe — анализ исходного видео.</summary>
    Ffprobe,

    /// <summary>Real-ESRGAN ncnn Vulkan — апскейл.</summary>
    RealEsrgan,

    /// <summary>RIFE ncnn Vulkan — интерполяция.</summary>
    Rife,
}

/// <summary>
/// Состояние одного инструмента: найден ли, где лежит исполняемый файл, каталог моделей
/// (для нейросетей) и версия из ресурсов файла, если она заполнена.
/// </summary>
/// <param name="Kind">Вид инструмента.</param>
/// <param name="DisplayName">Имя для журнала и UI.</param>
/// <param name="IsAvailable">Инструмент готов к работе (exe и, для нейросетей, модели найдены).</param>
/// <param name="ExecutablePath">Найденный путь к exe или <see langword="null"/>.</param>
/// <param name="ModelsDirectory">Каталог моделей (Real-ESRGAN — <c>models</c>, RIFE — <c>rife-v4*</c>) или <see langword="null"/>.</param>
/// <param name="Version">Версия из ресурсов exe; <see langword="null"/>, если не заполнена.</param>
public sealed record ToolStatus(
    ToolKind Kind,
    string DisplayName,
    bool IsAvailable,
    string? ExecutablePath,
    string? ModelsDirectory = null,
    string? Version = null);

/// <summary>Полный набор путей, готовый для пайплайна (эквивалент legacy dataclass <c>Tools</c>).</summary>
/// <param name="ToolsDirectory">Корень папки <c>tools</c>, где найдены инструменты.</param>
/// <param name="Ffmpeg">Путь к <c>ffmpeg.exe</c>.</param>
/// <param name="Ffprobe">Путь к <c>ffprobe.exe</c>.</param>
/// <param name="RealEsrgan">Путь к <c>realesrgan-ncnn-vulkan.exe</c>.</param>
/// <param name="RealEsrganModels">Каталог моделей Real-ESRGAN (<c>-m</c>).</param>
/// <param name="Rife">Путь к <c>rife-ncnn-vulkan.exe</c>.</param>
/// <param name="RifeModel">Каталог модели RIFE (<c>-m</c>).</param>
public sealed record ToolPaths(
    string ToolsDirectory,
    string Ffmpeg,
    string Ffprobe,
    string RealEsrgan,
    string RealEsrganModels,
    string Rife,
    string RifeModel);

/// <summary>
/// Состояние всех инструментов в одном каталоге <c>tools</c>. Пайплайн может работать,
/// только когда <see cref="AllAvailable"/> истинно.
/// </summary>
/// <param name="ToolsDirectory">Корень проверенной папки <c>tools</c>.</param>
/// <param name="Ffmpeg">Состояние FFmpeg.</param>
/// <param name="Ffprobe">Состояние ffprobe.</param>
/// <param name="RealEsrgan">Состояние Real-ESRGAN.</param>
/// <param name="Rife">Состояние RIFE.</param>
public sealed record ToolsStatus(
    string ToolsDirectory,
    ToolStatus Ffmpeg,
    ToolStatus Ffprobe,
    ToolStatus RealEsrgan,
    ToolStatus Rife)
{
    /// <summary>Все четыре инструмента готовы к работе.</summary>
    public bool AllAvailable =>
        Ffmpeg.IsAvailable && Ffprobe.IsAvailable && RealEsrgan.IsAvailable && Rife.IsAvailable;

    /// <summary>Сколько инструментов готово (0–4) — для выбора лучшего каталога при поиске.</summary>
    public int AvailableCount =>
        (Ffmpeg.IsAvailable ? 1 : 0)
        + (Ffprobe.IsAvailable ? 1 : 0)
        + (RealEsrgan.IsAvailable ? 1 : 0)
        + (Rife.IsAvailable ? 1 : 0);

    /// <summary>Состояния всех инструментов в порядке <see cref="ToolKind"/>.</summary>
    public IReadOnlyList<ToolStatus> All => new[] { Ffmpeg, Ffprobe, RealEsrgan, Rife };

    /// <summary>Отображаемые имена ненайденных инструментов.</summary>
    public IReadOnlyList<string> MissingNames =>
        All.Where(status => !status.IsAvailable).Select(status => status.DisplayName).ToArray();

    /// <summary>
    /// Возвращает полный набор путей, если все инструменты готовы; иначе <see langword="null"/>.
    /// </summary>
    /// <returns>Пути для пайплайна или <see langword="null"/>.</returns>
    public ToolPaths? TryGetPaths()
    {
        if (!AllAvailable)
        {
            return null;
        }

        return new ToolPaths(
            ToolsDirectory,
            Ffmpeg.ExecutablePath!,
            Ffprobe.ExecutablePath!,
            RealEsrgan.ExecutablePath!,
            RealEsrgan.ModelsDirectory!,
            Rife.ExecutablePath!,
            Rife.ModelsDirectory!);
    }
}

/// <summary>
/// Поиск нативных инструментов: сначала <c>tools</c> рядом с исполняемым файлом
/// (<see cref="Environment.ProcessPath"/>), затем <c>tools</c> в текущем каталоге.
/// Внутри каталога exe ищется рекурсивно, как legacy <c>ToolManager._find_exe</c>;
/// для Real-ESRGAN обязателен каталог <c>models</c> с <c>*.param</c>, для RIFE —
/// непустой каталог <c>rife-v4.6</c> (или <c>rife-v4*</c>).
/// </summary>
public sealed class ToolsLocator
{
    private static readonly EnumerationOptions SearchOptions = new()
    {
        RecurseSubdirectories = true,
        IgnoreInaccessible = true,
        MatchCasing = MatchCasing.CaseInsensitive,
        AttributesToSkip = FileAttributes.ReparsePoint,
        ReturnSpecialDirectories = false,
    };

    /// <summary>Создаёт локатор.</summary>
    /// <param name="appDirectory">
    /// Каталог приложения; <see langword="null"/> — каталог <see cref="Environment.ProcessPath"/>,
    /// затем <see cref="AppContext.BaseDirectory"/>.
    /// </param>
    /// <param name="workingDirectory">Текущий каталог; <see langword="null"/> — <see cref="Environment.CurrentDirectory"/>.</param>
    public ToolsLocator(string? appDirectory = null, string? workingDirectory = null)
    {
        AppDirectory = ResolveAppDirectory(appDirectory);
        WorkingDirectory = Path.GetFullPath(workingDirectory ?? Environment.CurrentDirectory);

        var roots = new List<string> { Path.Combine(AppDirectory, "tools") };
        var workingTools = Path.Combine(WorkingDirectory, "tools");
        if (!string.Equals(roots[0], workingTools, StringComparison.OrdinalIgnoreCase))
        {
            roots.Add(workingTools);
        }

        SearchDirectories = roots.AsReadOnly();
    }

    /// <summary>Каталог приложения, рядом с которым ищется <c>tools</c>.</summary>
    public string AppDirectory { get; }

    /// <summary>Текущий каталог процесса — второй корень поиска.</summary>
    public string WorkingDirectory { get; }

    /// <summary>Основной каталог инструментов: <c>tools</c> рядом с приложением.</summary>
    public string PrimaryToolsDirectory => Path.Combine(AppDirectory, "tools");

    /// <summary>Все каталоги поиска в порядке приоритета (без дублей).</summary>
    public IReadOnlyList<string> SearchDirectories { get; }

    /// <summary>
    /// Ищет инструменты во всех каталогах поиска. Возвращает первый полный набор;
    /// если полного нет — каталог с наибольшим числом найденных инструментов.
    /// </summary>
    /// <returns>Состояние инструментов; пути могут быть <see langword="null"/> для ненайденных.</returns>
    public ToolsStatus Locate()
    {
        ToolsStatus? best = null;
        foreach (var root in SearchDirectories)
        {
            var status = LocateInDirectory(root);
            if (status.AllAvailable)
            {
                return status;
            }

            if (best is null || status.AvailableCount > best.AvailableCount)
            {
                best = status;
            }
        }

        return best ?? LocateInDirectory(PrimaryToolsDirectory);
    }

    /// <summary>
    /// Проверяет один каталог <c>tools</c> (например, после скачивания).
    /// </summary>
    /// <param name="toolsDirectory">Корень папки <c>tools</c>.</param>
    /// <returns>Состояние инструментов в этом каталоге.</returns>
    public static ToolsStatus LocateInDirectory(string toolsDirectory)
    {
        if (string.IsNullOrWhiteSpace(toolsDirectory))
        {
            throw new ArgumentException("Каталог инструментов не задан.", nameof(toolsDirectory));
        }

        var root = Path.GetFullPath(toolsDirectory);
        var ffmpeg = FindFile(root, "ffmpeg.exe");
        var ffprobe = FindFile(root, "ffprobe.exe");
        var realEsrgan = FindFile(root, "realesrgan-ncnn-vulkan.exe");
        var rife = FindFile(root, "rife-ncnn-vulkan.exe");
        var realEsrganModels = FindModelsDirectory(realEsrgan);
        var rifeModel = FindRifeModelDirectory(rife);

        return new ToolsStatus(
            root,
            CreateStatus(ToolKind.Ffmpeg, "FFmpeg", ffmpeg, null, ffmpeg is not null),
            CreateStatus(ToolKind.Ffprobe, "ffprobe", ffprobe, null, ffprobe is not null),
            CreateStatus(
                ToolKind.RealEsrgan,
                "Real-ESRGAN",
                realEsrgan,
                realEsrganModels,
                realEsrgan is not null && realEsrganModels is not null),
            CreateStatus(
                ToolKind.Rife,
                "RIFE",
                rife,
                rifeModel,
                rife is not null && rifeModel is not null));
    }

    private static ToolStatus CreateStatus(
        ToolKind kind,
        string displayName,
        string? executablePath,
        string? modelsDirectory,
        bool isAvailable) =>
        new(kind, displayName, isAvailable, executablePath, modelsDirectory, TryGetVersion(executablePath));

    private static string ResolveAppDirectory(string? appDirectory)
    {
        if (!string.IsNullOrWhiteSpace(appDirectory))
        {
            return Path.GetFullPath(appDirectory);
        }

        var processPath = Environment.ProcessPath;
        if (!string.IsNullOrWhiteSpace(processPath))
        {
            var directory = Path.GetDirectoryName(processPath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                return Path.GetFullPath(directory);
            }
        }

        return Path.GetFullPath(AppContext.BaseDirectory);
    }

    private static string? FindFile(string root, string fileName)
    {
        if (!Directory.Exists(root))
        {
            return null;
        }

        string? best = null;
        var bestDepth = int.MaxValue;

        try
        {
            foreach (var path in Directory.EnumerateFiles(root, fileName, SearchOptions))
            {
                var depth = GetDepth(root, path);
                if (depth < bestDepth
                    || (depth == bestDepth
                        && string.Compare(path, best, StringComparison.OrdinalIgnoreCase) < 0))
                {
                    best = path;
                    bestDepth = depth;
                }
            }
        }
        catch (IOException)
        {
            return best;
        }
        catch (UnauthorizedAccessException)
        {
            return best;
        }

        return best;
    }

    private static string? FindModelsDirectory(string? executablePath)
    {
        var executableDirectory = GetExecutableDirectory(executablePath);
        if (executableDirectory is null)
        {
            return null;
        }

        foreach (var directory in EnumerateDirectories(executableDirectory, "models"))
        {
            try
            {
                if (Directory.EnumerateFiles(directory, "*.param", SearchOption.TopDirectoryOnly).Any())
                {
                    return directory;
                }
            }
            catch (IOException)
            {
                // Пропускаем нечитаемый каталог.
            }
            catch (UnauthorizedAccessException)
            {
                // Пропускаем недоступный каталог.
            }
        }

        return null;
    }

    private static string? FindRifeModelDirectory(string? executablePath)
    {
        var executableDirectory = GetExecutableDirectory(executablePath);
        if (executableDirectory is null)
        {
            return null;
        }

        foreach (var directory in EnumerateDirectories(executableDirectory, "rife-v4.6"))
        {
            if (HasAnyEntries(directory))
            {
                return directory;
            }
        }

        foreach (var directory in EnumerateDirectories(executableDirectory, "rife-v4*"))
        {
            if (HasAnyEntries(directory))
            {
                return directory;
            }
        }

        return null;
    }

    private static string? GetExecutableDirectory(string? executablePath)
    {
        if (string.IsNullOrWhiteSpace(executablePath))
        {
            return null;
        }

        var directory = Path.GetDirectoryName(executablePath);
        return !string.IsNullOrWhiteSpace(directory) && Directory.Exists(directory)
            ? directory
            : null;
    }

    private static IEnumerable<string> EnumerateDirectories(string root, string pattern)
    {
        var candidates = new List<string>();
        try
        {
            candidates.AddRange(Directory.EnumerateDirectories(root, pattern, SearchOptions));
        }
        catch (IOException)
        {
            return Array.Empty<string>();
        }
        catch (UnauthorizedAccessException)
        {
            return Array.Empty<string>();
        }

        candidates.Sort((left, right) =>
        {
            var depthCompare = GetDepth(root, left).CompareTo(GetDepth(root, right));
            return depthCompare != 0
                ? depthCompare
                : string.Compare(left, right, StringComparison.OrdinalIgnoreCase);
        });

        return candidates;
    }

    private static bool HasAnyEntries(string directory)
    {
        try
        {
            return Directory.EnumerateFileSystemEntries(directory).Any();
        }
        catch (IOException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static int GetDepth(string root, string path)
    {
        var relative = Path.GetRelativePath(root, path);
        return relative.Split(
            [Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar],
            StringSplitOptions.RemoveEmptyEntries).Length;
    }

    private static string? TryGetVersion(string? executablePath)
    {
        if (string.IsNullOrWhiteSpace(executablePath))
        {
            return null;
        }

        try
        {
            var info = FileVersionInfo.GetVersionInfo(executablePath);
            var version = info.FileVersion ?? info.ProductVersion;
            return string.IsNullOrWhiteSpace(version) ? null : version.Trim();
        }
        catch (Exception)
        {
            // Версия необязательна: отсутствие ресурсов не делает инструмент неготовым.
            return null;
        }
    }
}
