using System.Collections.Specialized;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VideoBoost.App.Services;

namespace VideoBoost.App.Views.Controls;

/// <summary>
/// Нижняя панель журнала: виртуализованный список строк, авто-скролл к последней,
/// пустое состояние. Источник — <see cref="LogService.Instance"/> (потокобезопасен).
/// </summary>
public sealed partial class JournalPanel : UserControl
{
    private readonly LogService _log = LogService.Instance;
    private bool _subscribed;

    /// <summary>Создаёт панель и подключает её к журналу приложения.</summary>
    public JournalPanel()
    {
        InitializeComponent();
        JournalLines.ItemsSource = _log.Entries;
        RefreshEmptyState();

        Loaded += JournalPanel_Loaded;
        Unloaded += JournalPanel_Unloaded;
    }

    private void JournalPanel_Loaded(object sender, RoutedEventArgs e)
    {
        Subscribe();
        RefreshEmptyState();
        ScrollToEnd();
    }

    private void JournalPanel_Unloaded(object sender, RoutedEventArgs e) => Unsubscribe();

    private void Subscribe()
    {
        if (_subscribed)
        {
            return;
        }

        _log.Entries.CollectionChanged += Entries_CollectionChanged;
        _subscribed = true;
    }

    private void Unsubscribe()
    {
        if (!_subscribed)
        {
            return;
        }

        _log.Entries.CollectionChanged -= Entries_CollectionChanged;
        _subscribed = false;
    }

    private void Entries_CollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        RefreshEmptyState();

        if (e.Action == NotifyCollectionChangedAction.Add)
        {
            ScrollToEnd();
        }
    }

    private void ScrollToEnd()
    {
        if (_log.Entries.Count == 0)
        {
            return;
        }

        LogEntry last = _log.Entries[^1];

        // После добавления нужен один проход layout, иначе контейнер ещё не создан.
        DispatcherQueue.TryEnqueue(() => JournalLines.ScrollIntoView(last));
    }

    private void RefreshEmptyState()
    {
        bool isEmpty = _log.Entries.Count == 0;
        JournalEmptyState.Visibility = isEmpty ? Visibility.Visible : Visibility.Collapsed;
        JournalLines.Visibility = isEmpty ? Visibility.Collapsed : Visibility.Visible;
    }
}
