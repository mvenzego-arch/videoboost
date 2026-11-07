using System.Diagnostics;
using System.IO.Compression;
using System.Net.Http;

namespace VideoBoost.Engine.Tools;

/// <summary>Вид скачиваемого пакета инструментов.</summary>
public enum ToolPackageKind
{
    /// <summary>FFmpeg (ffmpeg.exe + ffprobe.exe).</summary>
    Ffmpeg,

    /// <summary>Real-ESRGAN ncnn Vulkan с каталогом models.</summary>
    RealEsrgan,

    /// <summary>RIFE ncnn Vulkan с моделями rife-v4*.</summary>
    Rife,
}

/// <summary>
/// Описание пакета инструментов: URL релиза, ожидаемый exe, папка распаковки и
/// приблизительный вес для взвешенного прогресса. URL-адреса взяты из legacy
/// <c>engine.py</c> без изменений.
/// </summary>
/// <param name="Kind">Вид пакета.</param>
/// <param name="Title">Отображаемое имя («FFmpeg», «Real-ESRGAN», «RIFE»).</param>
/// <param name="DownloadUrl">Точный URL zip-архива из legacy.</param>
/// <param name="ExecutableName">Имя ожидаемого исполняемого файла.</param>
/// <param name="DirectoryName">Подкаталог <c>tools</c> для распаковки (и имя zip в downloads).</param>
/// <param name="WeightMegabytes">Приблизительный размер в МБ для взвешенного прогресса.</param>
public sealed record ToolPackage(
    ToolPackageKind Kind,
    string Title,
    string DownloadUrl,
    string ExecutableName,
    string DirectoryName,
    int WeightMegabytes);

/// <summary>
/// Прогресс скачивания/распаковки инструментов. <see cref="Percent"/> — общий прогресс
/// всех недостающих пакетов (0–100), <see cref="BytesReceived"/>/<see cref="TotalBytes"/> —
/// текущий пакет (0 в <see cref="TotalBytes"/> — размер неизвестен), <see cref="Message"/> —
/// готовая строка для журнала.
/// </summary>
/// <param name="Package">Пакет, к которому относится сообщение.</param>
/// <param name="Title">Отображаемое имя пакета.</param>
/// <param name="Percent">Общий прогресс скачивания в процентах (0–100).</param>
/// <param name="BytesReceived">Скачано байт текущего пакета.</param>
/// <param name="TotalBytes">Размер текущего пакета в байтах; 0 — неизвестен.</param>
/// <param name="Message">Строка для журнала.</param>
public sealed record ToolDownloadProgress(
    ToolPackageKind Package,
    string Title,
    double Percent,
    long BytesReceived,
    long TotalBytes,
    string Message);

/// <summary>
/// Ошибка скачивания/распаковки инструментов с сохранением пакета и URL для
/// сообщения пользователю (по аналогии с legacy <c>EngineError</c>).
/// </summary>
public sealed class ToolsDownloadException : Exception
{
    /// <summary>Создаёт исключение скачивания инструментов.</summary>
    /// <param name="message">Сообщение для журнала.</param>
    /// <param name="package">Пакет, на котором произошла ошибка, или <see langword="null"/>.</param>
    /// <param name="downloadUrl">URL пакета или <see langword="null"/>.</param>
    /// <param name="innerException">Исходная ошибка сети/архива или <see langword="null"/>.</param>
    public ToolsDownloadException(
        string message,
        ToolPackageKind? package = null,
        string? downloadUrl = null,
        Exception? innerException = null)
        : base(message, innerException)
    {
        Package = package;
        DownloadUrl = downloadUrl;
    }

    /// <summary>Пакет, на котором произошла ошибка, если известен.</summary>
    public ToolPackageKind? Package { get; }

    /// <summary>URL пакета, если известен.</summary>
    public string? DownloadUrl { get; }
}

/// <summary>
/// Скачивание недостающих инструментов в папку <c>tools</c> с повторами при обрыве
/// сети (3 попытки, как legacy <c>ToolManager._download</c>) и распаковкой zip.
/// После скачивания выполняется повторная проверка через <see cref="ToolsLocator"/>.
/// </summary>
public sealed class ToolsDownloader : IDisposable
{
    /// <summary>User-Agent из legacy (GitHub отдаёт архивы и без него, но заголовок сохранён).</summary>
    public const string UserAgent =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        + "(KHTML, like Gecko) Chrome/124.0 Safari/537.36";

    private const int MaxAttempts = 3;
    private const int BufferSize = 256 * 1024;

    private static readonly ToolPackage[] PackageArray =
    [
        new ToolPackage(
            ToolPackageKind.Ffmpeg,
            "FFmpeg",
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n9.0-latest-win64-gpl-9.0.zip",
            "ffmpeg.exe",
            "ffmpeg",
            195),
        new ToolPackage(
            ToolPackageKind.RealEsrgan,
            "Real-ESRGAN",
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
            "realesrgan-ncnn-vulkan.exe",
            "realesrgan",
            46),
        new ToolPackage(
            ToolPackageKind.Rife,
            "RIFE",
            "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip",
            "rife-ncnn-vulkan.exe",
            "rife",
            432),
    ];

    private static readonly IReadOnlyList<ToolPackage> PackageView = Array.AsReadOnly(PackageArray);

    private readonly string _toolsDirectory;
    private readonly HttpClient _httpClient;
    private readonly bool _ownsHttpClient;
    private bool _disposed;

    /// <summary>Создаёт загрузчик инструментов.</summary>
    /// <param name="toolsDirectory">Корень папки <c>tools</c> (создаётся при необходимости).</param>
    /// <param name="httpClient">
    /// Внешний <see cref="HttpClient"/> (для тестов); <see langword="null"/> — собственный
    /// клиент без общего таймаута, отмена через <see cref="CancellationToken"/>.
    /// </param>
    public ToolsDownloader(string toolsDirectory, HttpClient? httpClient = null)
    {
        if (string.IsNullOrWhiteSpace(toolsDirectory))
        {
            throw new ArgumentException("Каталог инструментов не задан.", nameof(toolsDirectory));
        }

        _toolsDirectory = Path.GetFullPath(toolsDirectory);
        _ownsHttpClient = httpClient is null;
        _httpClient = httpClient ?? new HttpClient { Timeout = Timeout.InfiniteTimeSpan };
    }

    /// <summary>Корень папки <c>tools</c>, в которую скачиваются архивы.</summary>
    public string ToolsDirectory => _toolsDirectory;

    /// <summary>Каталог <c>tools/downloads</c> для zip-архивов (как в legacy).</summary>
    public string DownloadsDirectory => Path.Combine(_toolsDirectory, "downloads");

    /// <summary>Полный список пакетов и точных URL из legacy.</summary>
    public static IReadOnlyList<ToolPackage> Packages => PackageView;

    /// <summary>
    /// Проверяет инструменты и скачивает недостающие пакеты с повторами (3 попытки)
    /// и распаковкой в <c>tools/&lt;key&gt;</c>. При отмене выбрасывает
    /// <see cref="OperationCanceledException"/>; после успеха повторно проверяет
    /// <see cref="ToolsLocator.LocateInDirectory"/>.
    /// </summary>
    /// <param name="progress">Необязательный прогресс скачивания/распаковки.</param>
    /// <param name="cancellationToken">Отмена скачивания и распаковки.</param>
    /// <returns>Итоговое состояние инструментов (все доступны).</returns>
    /// <exception cref="ToolsDownloadException">Сеть, архив или итоговая проверка не удались.</exception>
    /// <exception cref="OperationCanceledException">Скачивание отменено.</exception>
    public async Task<ToolsStatus> EnsureToolsAsync(
        IProgress<ToolDownloadProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(ToolsDownloader));
        }

        cancellationToken.ThrowIfCancellationRequested();

        var current = ToolsLocator.LocateInDirectory(_toolsDirectory);
        if (current.AllAvailable)
        {
            progress?.Report(new ToolDownloadProgress(
                ToolPackageKind.Ffmpeg, "Инструменты", 100d, 0, 0, "Инструменты готовы"));
            return current;
        }

        var missing = PackageArray
            .Where(package => !IsPackageReady(current, package.Kind))
            .ToArray();
        var totalWeight = missing.Sum(package => package.WeightMegabytes);
        if (totalWeight <= 0)
        {
            totalWeight = Math.Max(1, missing.Length);
        }

        var completedWeight = 0;
        foreach (var package in missing)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var basePercent = 100d * completedWeight / totalWeight;
            var spanPercent = 100d * package.WeightMegabytes / totalWeight;
            var zipPath = Path.Combine(DownloadsDirectory, package.DirectoryName + ".zip");

            void ReportDownload(double fraction, long received, long total, string message)
            {
                var percent = Math.Min(99d, basePercent + (spanPercent * 0.85 * Math.Clamp(fraction, 0d, 1d)));
                progress?.Report(new ToolDownloadProgress(
                    package.Kind, package.Title, percent, received, total, message));
            }

            void ReportExtraction(double fraction, int currentFile, int totalFiles)
            {
                var percent = Math.Min(99d, basePercent + (spanPercent * (0.85 + (0.15 * Math.Clamp(fraction, 0d, 1d)))));
                var message = $"Распаковка {package.Title}: {currentFile}/{totalFiles}";
                progress?.Report(new ToolDownloadProgress(
                    package.Kind, package.Title, percent, 0, 0, message));
            }

            try
            {
                await DownloadPackageAsync(package, zipPath, ReportDownload, cancellationToken)
                    .ConfigureAwait(false);
                await ExtractPackageAsync(package, zipPath, ReportExtraction, cancellationToken)
                    .ConfigureAwait(false);
                TryDeleteFile(zipPath);
            }
            finally
            {
                TryDeleteFile(zipPath + ".part");
            }

            completedWeight += package.WeightMegabytes;
            var donePercent = Math.Min(99d, 100d * completedWeight / totalWeight);
            progress?.Report(new ToolDownloadProgress(
                package.Kind, package.Title, donePercent, 0, 0, $"{package.Title}: готово"));
        }

        var result = ToolsLocator.LocateInDirectory(_toolsDirectory);
        if (!result.AllAvailable)
        {
            var missingNames = string.Join(", ", result.MissingNames);
            throw new ToolsDownloadException(
                $"Инструменты скачались, но не найдены в «{_toolsDirectory}». "
                + $"Проверьте папку tools или установите вручную. Отсутствуют: {missingNames}.");
        }

        progress?.Report(new ToolDownloadProgress(
            ToolPackageKind.Ffmpeg, "Инструменты", 100d, 0, 0, "Инструменты готовы"));
        return result;
    }

    /// <inheritdoc />
    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        if (_ownsHttpClient)
        {
            _httpClient.Dispose();
        }
    }

    private static bool IsPackageReady(ToolsStatus status, ToolPackageKind kind) => kind switch
    {
        ToolPackageKind.Ffmpeg => status.Ffmpeg.IsAvailable && status.Ffprobe.IsAvailable,
        ToolPackageKind.RealEsrgan => status.RealEsrgan.IsAvailable,
        ToolPackageKind.Rife => status.Rife.IsAvailable,
        _ => false,
    };

    private async Task DownloadPackageAsync(
        ToolPackage package,
        string zipPath,
        Action<double, long, long, string> report,
        CancellationToken cancellationToken)
    {
        var downloadsDirectory = Path.GetDirectoryName(zipPath);
        if (!string.IsNullOrWhiteSpace(downloadsDirectory))
        {
            Directory.CreateDirectory(downloadsDirectory);
        }

        var partPath = zipPath + ".part";
        Exception? lastError = null;

        for (var attempt = 1; attempt <= MaxAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            TryDeleteFile(partPath);

            try
            {
                await DownloadOnceAsync(package, partPath, report, cancellationToken).ConfigureAwait(false);
                File.Move(partPath, zipPath, overwrite: true);
                return;
            }
            catch (OperationCanceledException)
            {
                TryDeleteFile(partPath);
                throw;
            }
            catch (Exception exception)
            {
                lastError = exception;
                TryDeleteFile(partPath);
                if (attempt < MaxAttempts)
                {
                    await Task.Delay(TimeSpan.FromSeconds(2 * attempt), cancellationToken).ConfigureAwait(false);
                }
            }
        }

        throw new ToolsDownloadException(
            $"Не удалось скачать {package.Title}: {lastError?.Message}{Environment.NewLine}"
            + $"Ссылка: {package.DownloadUrl}",
            package.Kind,
            package.DownloadUrl,
            lastError);
    }

    private async Task DownloadOnceAsync(
        ToolPackage package,
        string partPath,
        Action<double, long, long, string> report,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, package.DownloadUrl);
        request.Headers.UserAgent.ParseAdd(UserAgent);
        request.Headers.Accept.ParseAdd("*/*");

        using var response = await _httpClient
            .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
            .ConfigureAwait(false);
        response.EnsureSuccessStatusCode();

        var totalBytes = response.Content.Headers.ContentLength ?? 0;
        await using var source = await response.Content
            .ReadAsStreamAsync(cancellationToken)
            .ConfigureAwait(false);
        await using var destination = new FileStream(
            partPath,
            FileMode.Create,
            FileAccess.Write,
            FileShare.None,
            BufferSize,
            useAsync: true);

        var buffer = new byte[BufferSize];
        long received = 0;
        var stopwatch = Stopwatch.StartNew();
        var lastReport = TimeSpan.Zero;

        while (true)
        {
            var read = await source.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken)
                .ConfigureAwait(false);
            if (read == 0)
            {
                break;
            }

            await destination.WriteAsync(buffer.AsMemory(0, read), cancellationToken)
                .ConfigureAwait(false);
            received += read;

            var elapsed = stopwatch.Elapsed;
            if (elapsed - lastReport >= TimeSpan.FromMilliseconds(250) || received == totalBytes)
            {
                lastReport = elapsed;
                var fraction = totalBytes > 0 ? (double)received / totalBytes : 0d;
                var receivedMegabytes = received / 1048576d;
                var speed = receivedMegabytes / Math.Max(0.5, elapsed.TotalSeconds);
                var message = totalBytes > 0
                    ? $"{package.Title}: {receivedMegabytes:0} / {totalBytes / 1048576d:0} МБ · {speed:0.0} МБ/с"
                    : $"{package.Title}: {receivedMegabytes:0} МБ · {speed:0.0} МБ/с";
                report(fraction, received, totalBytes, message);
            }
        }

        await destination.FlushAsync(cancellationToken).ConfigureAwait(false);
        stopwatch.Stop();

        if (totalBytes > 0 && received != totalBytes)
        {
            throw new IOException($"Соединение оборвалось: получено {received} из {totalBytes} байт.");
        }

        report(1d, received, totalBytes, $"{package.Title}: загрузка завершена");
    }

    private async Task ExtractPackageAsync(
        ToolPackage package,
        string zipPath,
        Action<double, int, int> report,
        CancellationToken cancellationToken)
    {
        var destinationRoot = Path.GetFullPath(Path.Combine(_toolsDirectory, package.DirectoryName));
        Directory.CreateDirectory(destinationRoot);
        var destinationRootWithSeparator = destinationRoot.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;

        try
        {
            using var archive = ZipFile.OpenRead(zipPath);
            var entries = archive.Entries.Where(entry => entry.Name.Length > 0).ToArray();
            if (entries.Length == 0)
            {
                throw new ToolsDownloadException(
                    $"Архив {Path.GetFileName(zipPath)} пуст.",
                    package.Kind,
                    package.DownloadUrl);
            }

            var rifeKeepDirectories = package.Kind == ToolPackageKind.Rife
                ? PrepareRifeKeepDirectories(entries)
                : Array.Empty<string>();
            var total = Math.Max(1, entries.Length);

            for (var index = 0; index < entries.Length; index++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                var entry = entries[index];

                if (ShouldKeepEntry(entry.FullName, package.Kind, rifeKeepDirectories))
                {
                    var relativePath = entry.FullName
                        .Replace('/', Path.DirectorySeparatorChar)
                        .Replace('\\', Path.DirectorySeparatorChar);
                    var targetPath = Path.GetFullPath(Path.Combine(destinationRoot, relativePath));

                    // Защита от путей вида ../../ (как legacy _extract).
                    if (targetPath.StartsWith(destinationRootWithSeparator, StringComparison.OrdinalIgnoreCase))
                    {
                        var targetDirectory = Path.GetDirectoryName(targetPath);
                        if (!string.IsNullOrWhiteSpace(targetDirectory))
                        {
                            Directory.CreateDirectory(targetDirectory);
                        }

                        await using var input = entry.Open();
                        await using var output = new FileStream(
                            targetPath,
                            FileMode.Create,
                            FileAccess.Write,
                            FileShare.None,
                            81920,
                            useAsync: true);
                        await input.CopyToAsync(output, cancellationToken).ConfigureAwait(false);
                    }
                }

                var processed = index + 1;
                if (processed % 20 == 0 || processed == total)
                {
                    report((double)processed / total, processed, total);
                }
            }

            report(1d, total, total);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (ToolsDownloadException)
        {
            throw;
        }
        catch (InvalidDataException exception)
        {
            throw new ToolsDownloadException(
                $"Архив {Path.GetFileName(zipPath)} повреждён или скачан не полностью. "
                + "Удалите папку tools/downloads и попробуйте снова.",
                package.Kind,
                package.DownloadUrl,
                exception);
        }
        catch (Exception exception)
        {
            throw new ToolsDownloadException(
                $"Ошибка распаковки {package.Title}: {exception.Message}",
                package.Kind,
                package.DownloadUrl,
                exception);
        }
    }

    private static IReadOnlyList<string> PrepareRifeKeepDirectories(IEnumerable<ZipArchiveEntry> entries)
    {
        var modelDirectories = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in entries)
        {
            var parts = SplitZipPath(entry.FullName);
            var modelsIndex = Array.FindIndex(
                parts,
                part => part.Equals("models", StringComparison.OrdinalIgnoreCase));
            if (modelsIndex >= 0 && modelsIndex + 1 < parts.Length && parts[modelsIndex + 1].Length > 0)
            {
                modelDirectories.Add(parts[modelsIndex + 1]);
            }
        }

        var preferred = modelDirectories
            .Where(directory => directory.Equals("rife-v4.6", StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (preferred.Length == 0)
        {
            preferred = modelDirectories
                .Where(directory => directory.StartsWith("rife-v4", StringComparison.OrdinalIgnoreCase))
                .ToArray();
        }

        if (preferred.Length == 0)
        {
            preferred = modelDirectories
                .OrderBy(directory => directory, StringComparer.OrdinalIgnoreCase)
                .ToArray();
        }

        return preferred;
    }

    private static bool ShouldKeepEntry(
        string fullName,
        ToolPackageKind kind,
        IReadOnlyList<string> rifeKeepDirectories)
    {
        var parts = SplitZipPath(fullName);
        if (parts.Length == 0)
        {
            return false;
        }

        switch (kind)
        {
            case ToolPackageKind.Ffmpeg:
                var fileName = parts[^1];
                return fileName.Equals("ffmpeg.exe", StringComparison.OrdinalIgnoreCase)
                    || fileName.Equals("ffprobe.exe", StringComparison.OrdinalIgnoreCase);

            case ToolPackageKind.RealEsrgan:
                return true;

            case ToolPackageKind.Rife:
                var modelsIndex = Array.FindIndex(
                    parts,
                    part => part.Equals("models", StringComparison.OrdinalIgnoreCase));
                if (modelsIndex < 0)
                {
                    return true;
                }

                if (modelsIndex + 1 >= parts.Length)
                {
                    return false;
                }

                return rifeKeepDirectories.Any(directory =>
                    directory.Equals(parts[modelsIndex + 1], StringComparison.OrdinalIgnoreCase));

            default:
                return false;
        }
    }

    private static string[] SplitZipPath(string path) =>
        path.Replace('\\', '/').Split('/', StringSplitOptions.RemoveEmptyEntries);

    private static void TryDeleteFile(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch (IOException)
        {
            // Временный файл занят — не мешаем основной ошибке.
        }
        catch (UnauthorizedAccessException)
        {
            // Нет прав на удаление — оставляем файл для следующего запуска.
        }
    }
}
