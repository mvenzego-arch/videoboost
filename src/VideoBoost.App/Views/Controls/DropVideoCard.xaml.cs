using System.Collections.ObjectModel;
using System.IO;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VideoBoost.App.Services;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage;
using Windows.Storage.Pickers;

namespace VideoBoost.App.Views.Controls;

/// <summary>
/// Левая карточка видео: drop-зона пустого состояния, список файлов, добавление/удаление.
/// Обработчики drag&amp;drop стабильны (не падают); полная логика движка — iteration 2.
/// </summary>
public sealed partial class DropVideoCard : UserControl
{
    private static readonly string[] VideoExtensions =
    [
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv",
        ".flv", ".ts", ".mts", ".m2ts", ".mpg", ".mpeg", ".3gp",
    ];

    private readonly ObservableCollection<VideoItem> _videos = [];

    /// <summary>Создаёт карточку видео.</summary>
    public DropVideoCard()
    {
        InitializeComponent();
        VideoList.ItemsSource = _videos;
        RefreshState();
    }

    /// <summary>Срабатывает после изменения списка видео; аргумент — новое количество.</summary>
    public event EventHandler<int>? VideoCountChanged;

    /// <summary>Файлы, добавленные пользователем (для движка; iteration 2).</summary>
    public IReadOnlyList<VideoItem> Videos => _videos;

    /// <summary>Количество добавленных видео.</summary>
    public int VideoCount => _videos.Count;

    private void AddVideosButton_Click(object sender, RoutedEventArgs e)
    {
        _ = AddVideosFromPickerAsync();
    }

    private async Task AddVideosFromPickerAsync()
    {
        try
        {
            FileOpenPicker picker = new();
            picker.SuggestedStartLocation = PickerLocationId.VideosLibrary;
            foreach (string extension in VideoExtensions)
            {
                picker.FileTypeFilter.Add(extension);
            }

            Window? window = App.MainWindowInstance;
            if (window is not null)
            {
                nint hwnd = WinRT.Interop.WindowNative.GetWindowHandle(window);
                WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            }

            IReadOnlyList<StorageFile> files = await picker.PickMultipleFilesAsync();
            List<string> paths = files.Select(file => file.Path).ToList();
            if (paths.Count == 0)
            {
                return;
            }

            int added = AddFiles(paths, out int skipped);
            if (added > 0)
            {
                LogService.Instance.Info($"Добавлено видео: {added}.");
            }

            if (skipped > 0)
            {
                LogService.Instance.Warning($"Пропущено файлов: {skipped} (не видео или уже в списке).");
            }
        }
        catch (Exception ex)
        {
            LogService.Instance.Error($"Не удалось открыть выбор файлов: {ex.Message}");
        }
    }

    private void RemoveVideosButton_Click(object sender, RoutedEventArgs e)
    {
        List<VideoItem> selected = VideoList.SelectedItems.OfType<VideoItem>().ToList();
        foreach (VideoItem item in selected)
        {
            _videos.Remove(item);
        }

        RefreshState();
    }

    private void ClearVideosButton_Click(object sender, RoutedEventArgs e)
    {
        VideoList.SelectedItems.Clear();
        _videos.Clear();
        RefreshState();
    }

    private void RemoveItem_Click(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement { DataContext: VideoItem item })
        {
            _videos.Remove(item);
            RefreshState();
        }
    }

    private void VideoList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        RemoveVideosButton.IsEnabled = VideoList.SelectedItems.Count > 0;
    }

    private void VideoDropTarget_DragOver(object sender, DragEventArgs e)
    {
        e.AcceptedOperation = e.DataView.Contains(StandardDataFormats.StorageItems)
            ? DataPackageOperation.Copy
            : DataPackageOperation.None;

        if (e.DragUIOverride is not null)
        {
            e.DragUIOverride.Caption = "Добавить видео";
            e.DragUIOverride.IsCaptionVisible = true;
        }
    }

    private void VideoDropTarget_DragLeave(object sender, DragEventArgs e)
    {
        // TODO(iteration 2): подсветка drop-зоны при DragEnter/DragLeave.
    }

    private async void VideoDropTarget_Drop(object sender, DragEventArgs e)
    {
        try
        {
            if (!e.DataView.Contains(StandardDataFormats.StorageItems))
            {
                return;
            }

            IReadOnlyList<IStorageItem> items = await e.DataView.GetStorageItemsAsync();
            List<string> paths = items.OfType<StorageFile>().Select(file => file.Path).ToList();
            int added = AddFiles(paths, out int skipped);

            if (added > 0)
            {
                LogService.Instance.Info($"Перетащено видео: {added}.");
            }

            if (skipped > 0)
            {
                LogService.Instance.Warning($"Пропущено файлов при перетаскивании: {skipped}.");
            }
        }
        catch (Exception ex)
        {
            LogService.Instance.Error($"Не удалось принять перетащенные файлы: {ex.Message}");
        }
    }

    private int AddFiles(IReadOnlyList<string> paths, out int skipped)
    {
        int added = 0;
        skipped = 0;

        foreach (string path in paths)
        {
            if (AddFile(path))
            {
                added++;
            }
            else
            {
                skipped++;
            }
        }

        if (added > 0)
        {
            RefreshState();
        }

        return added;
    }

    private bool AddFile(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path) || !IsVideoFile(path))
        {
            return false;
        }

        bool exists = _videos.Any(
            item => string.Equals(item.FullPath, path, StringComparison.OrdinalIgnoreCase));
        if (exists)
        {
            return false;
        }

        _videos.Add(new VideoItem(path));
        return true;
    }

    private static bool IsVideoFile(string path)
    {
        string extension = Path.GetExtension(path);
        return VideoExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Пустое состояние: drop-зона занимает карточку целиком.
    /// С файлами: компактная полка 40 px + список.
    /// </summary>
    private void RefreshState()
    {
        bool hasFiles = _videos.Count > 0;

        EmptyStatePanel.Visibility = hasFiles ? Visibility.Collapsed : Visibility.Visible;
        VideoList.Visibility = hasFiles ? Visibility.Visible : Visibility.Collapsed;

        DropRow.Height = hasFiles ? GridLength.Auto : new GridLength(1, GridUnitType.Star);
        ListRow.Height = hasFiles ? new GridLength(1, GridUnitType.Star) : new GridLength(0);

        VideoDropTarget.Height = hasFiles ? 40 : double.NaN;
        VideoDropTarget.MinHeight = hasFiles ? 40 : 180;
        VideoDropTarget.Padding = hasFiles ? new Thickness(8, 2, 8, 2) : new Thickness(16);

        FilesCountText.Text = hasFiles ? $"{_videos.Count} видео" : "Видео не выбраны";
        RemoveVideosButton.IsEnabled = VideoList.SelectedItems.Count > 0;
        ClearVideosButton.IsEnabled = hasFiles;

        VideoCountChanged?.Invoke(this, _videos.Count);
    }
}
