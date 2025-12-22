using System;
using System.Drawing;
using System.Windows.Forms;

namespace TrayApp
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            // Create a NotifyIcon (System Tray icon)
            NotifyIcon trayIcon = new NotifyIcon();
            trayIcon.Icon = SystemIcons.Application; // default app icon
            trayIcon.Text = "My Tray App";
            trayIcon.Visible = true;

            // Add a context menu
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem exitItem = new ToolStripMenuItem("Exit");
            exitItem.Click += (s, e) => Application.Exit();
            menu.Items.Add(exitItem);
            trayIcon.ContextMenuStrip = menu;

            // Optional: show balloon tip on start
            trayIcon.ShowBalloonTip(3000, "Tray App", "Application started!", ToolTipIcon.Info);

            // Run invisible application
            Application.Run();
        }
    }
}
