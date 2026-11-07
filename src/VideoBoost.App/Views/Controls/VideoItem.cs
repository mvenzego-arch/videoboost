using System.IO;

namespace VideoBoost.App.Views.Controls;

/// <summary>Видео в списке левой карточки: полный путь, имя и папка.</summary>
public sealed class VideoItem
{
    /// <summary>Создаёт элемент списка по полному пути.</summary>
    public VideoItem(string fullPath)
    {
        FullPath = fullPath;
        Name = Path.GetFileName(fullPath);
        Folder = Path.GetDirectoryName(fullPath) ?? string.Empty;
    }

    /// <summary>Полный путь к файлу (для движка и ToolTip).</summary>
    public string FullPath { get; }

    /// <summary>Имя файла без папки.</summary>
    public string Name { get; }

    /// <summary>Папка файла (подпись под именем).</summary>
    public string Folder { get; }
}
