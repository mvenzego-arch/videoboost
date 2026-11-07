using System.ComponentModel;
using System.Diagnostics;
using System.Text;
using VideoBoost.Engine.Commands;

namespace VideoBoost.Engine.Processes;

/// <summary>Поток вывода нативного процесса.</summary>
public enum OutputKind
{
    /// <summary>Стандартный поток вывода (stdout).</summary>
    StandardOutput,

    /// <summary>Поток ошибок (stderr).</summary>
    StandardError,
}

/// <summary>Одна строка, полученная от нативного процесса.</summary>
public sealed class ProcessLineEventArgs : EventArgs
{
    /// <summary>Создаёт событие строки вывода.</summary>
    /// <param name="kind">Поток, из которого пришла строка.</param>
    /// <param name="line">Текст строки без завершающего перевода.</param>
    public ProcessLineEventArgs(OutputKind kind, string line)
    {
        Kind = kind;
        Line = line;
    }

    /// <summary>Поток, из которого пришла строка.</summary>
    public OutputKind Kind { get; }

    /// <summary>Текст строки без завершающего перевода.</summary>
    public string Line { get; }
}

/// <summary>
/// Запуск нативных инструментов FFmpeg/Real-ESRGAN/RIFE с безопасным чтением
/// stdout и stderr. Реализация обязана не блокировать вызывающий поток, читать оба
/// потока одновременно и при отмене убивать дерево процессов.
/// </summary>
public interface IProcessRunner
{
    /// <summary>
    /// Событие приходит из фонового потока чтения соответствующего потока. Обработчик
    /// должен быть быстрым и потокобезопасным; исключения обработчика не прерывают чтение.
    /// </summary>
    event EventHandler<ProcessLineEventArgs>? LineReceived;

    /// <summary>Запускает команду и ждёт её завершения.</summary>
    /// <param name="command">Исполняемый файл, аргументы и рабочий каталог.</param>
    /// <param name="cancellationToken">Отмена: процесс и всё его дерево убиваются.</param>
    /// <returns>Код возврата и захваченные потоки завершившегося процесса.</returns>
    /// <exception cref="ProcessExecutionException">Процесс не удалось запустить.</exception>
    /// <exception cref="OperationCanceledException">Запуск отменён.</exception>
    Task<ProcessResult> RunAsync(NativeCommand command, CancellationToken cancellationToken = default);
}

/// <summary>
/// Универсальный раннер нативных процессов для движка. Использует
/// <c>ProcessStartInfo.ArgumentList</c> (без строковой склейки), UTF-8 для stdout/stderr,
/// фоновое чтение двух потоков (deadlock-безопасно) и
/// <c>Process.Kill(entireProcessTree: true)</c> при отмене.
/// </summary>
public sealed class ProcessRunner : IProcessRunner
{
    private const int DefaultMaxCapturedChars = 4 * 1024 * 1024;

    private readonly int _maxCapturedChars;

    /// <summary>Создаёт раннер.</summary>
    /// <param name="maxCapturedCharsPerStream">
    /// Лимит символов, сохраняемых из каждого потока (защита от гигантского вывода).
    /// Для ffprobe JSON этого лимита достаточно.
    /// </param>
    /// <exception cref="ArgumentOutOfRangeException">Лимит не положительный.</exception>
    public ProcessRunner(int maxCapturedCharsPerStream = DefaultMaxCapturedChars)
    {
        if (maxCapturedCharsPerStream <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(maxCapturedCharsPerStream),
                maxCapturedCharsPerStream,
                "Лимит захвата вывода должен быть положительным.");
        }

        _maxCapturedChars = maxCapturedCharsPerStream;
    }

    /// <inheritdoc />
    public event EventHandler<ProcessLineEventArgs>? LineReceived;

    /// <inheritdoc />
    public async Task<ProcessResult> RunAsync(
        NativeCommand command,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(command);
        if (string.IsNullOrWhiteSpace(command.FileName))
        {
            throw new ArgumentException("Путь к исполняемому файлу не задан.", nameof(command));
        }

        cancellationToken.ThrowIfCancellationRequested();
        var startInfo = CreateStartInfo(command);
        return await RunCoreAsync(startInfo, cancellationToken).ConfigureAwait(false);
    }

    private static ProcessStartInfo CreateStartInfo(NativeCommand command)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = command.FileName,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        var workingDirectory = command.WorkingDirectory;
        if (!string.IsNullOrWhiteSpace(workingDirectory))
        {
            startInfo.WorkingDirectory = workingDirectory;
        }

        foreach (var argument in command.Arguments)
        {
            ArgumentNullException.ThrowIfNull(argument, nameof(command));
            startInfo.ArgumentList.Add(argument);
        }

        return startInfo;
    }

    private async Task<ProcessResult> RunCoreAsync(
        ProcessStartInfo startInfo,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        using var process = new System.Diagnostics.Process { StartInfo = startInfo };

        try
        {
            if (!process.Start())
            {
                throw new ProcessExecutionException(
                    $"Не удалось запустить «{startInfo.FileName}»: Process.Start вернул false.",
                    new InvalidOperationException("Process.Start вернул false."));
            }
        }
        catch (Win32Exception exception)
        {
            throw new ProcessExecutionException(
                $"Не удалось запустить «{startInfo.FileName}»: {exception.Message}",
                exception);
        }

        var standardOutput = new CapturedText(_maxCapturedChars);
        var standardError = new CapturedText(_maxCapturedChars);

        var stdoutTask = PumpAsync(
            process.StandardOutput,
            OutputKind.StandardOutput,
            standardOutput,
            cancellationToken);
        var stderrTask = PumpAsync(
            process.StandardError,
            OutputKind.StandardError,
            standardError,
            cancellationToken);

        try
        {
            try
            {
                await process.WaitForExitAsync(cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                KillProcessTree(process);
                await ObservePumpsAfterCancellationAsync(stdoutTask, stderrTask).ConfigureAwait(false);
                throw;
            }

            await Task.WhenAll(stdoutTask, stderrTask).ConfigureAwait(false);
            stopwatch.Stop();
            return new ProcessResult(
                process.ExitCode,
                standardOutput.Text,
                standardError.Text,
                stopwatch.Elapsed);
        }
        finally
        {
            KillProcessTree(process);
            stopwatch.Stop();
        }
    }

    private async Task PumpAsync(
        StreamReader reader,
        OutputKind kind,
        CapturedText capture,
        CancellationToken cancellationToken)
    {
        try
        {
            while (true)
            {
                var line = await reader.ReadLineAsync(cancellationToken).ConfigureAwait(false);
                if (line is null)
                {
                    break;
                }

                capture.Append(line);
                RaiseLineReceived(kind, line);
            }
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (IOException)
        {
            // Процесс закрыл поток (например, убит) — это не ошибка чтения.
        }
        catch (ObjectDisposedException)
        {
            // Поток освобождён после завершения процесса.
        }
    }

    private void RaiseLineReceived(OutputKind kind, string line)
    {
        var handler = LineReceived;
        if (handler is null)
        {
            return;
        }

        try
        {
            handler(this, new ProcessLineEventArgs(kind, line));
        }
        catch (Exception)
        {
            // Подписчик не должен ломать чтение потоков и завершение процесса.
        }
    }

    private static async Task ObservePumpsAfterCancellationAsync(Task stdoutTask, Task stderrTask)
    {
        try
        {
            await Task.WhenAll(stdoutTask, stderrTask).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            // Ожидаемо: чтение отменено вместе с процессом.
        }
        catch (IOException)
        {
            // Поток закрылся при убийстве процесса.
        }
        catch (ObjectDisposedException)
        {
            // Поток освобождён при убийстве процесса.
        }
    }

    private static void KillProcessTree(System.Diagnostics.Process process)
    {
        try
        {
            if (process.HasExited)
            {
                return;
            }

            process.Kill(entireProcessTree: true);
            process.WaitForExit(5000);
        }
        catch (InvalidOperationException)
        {
            // Процесс уже завершился или не был запущен.
        }
        catch (Win32Exception)
        {
            // Процесс уже завершился между проверкой и Kill.
        }
        catch (NotSupportedException)
        {
            // Платформа не поддерживает убийство дерева — процесс уже мог завершиться.
        }
    }

    private sealed class CapturedText
    {
        private readonly StringBuilder _builder = new();
        private readonly int _limit;
        private bool _truncated;

        public CapturedText(int limit)
        {
            _limit = limit;
        }

        public string Text => _truncated
            ? _builder.ToString() + Environment.NewLine + "…[вывод усечён]"
            : _builder.ToString();

        public void Append(string line)
        {
            if (_truncated)
            {
                return;
            }

            if (_builder.Length + line.Length + 1 > _limit)
            {
                _truncated = true;
                return;
            }

            _builder.Append(line).Append('\n');
        }
    }
}
