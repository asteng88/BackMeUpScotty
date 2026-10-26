using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("BackMeUpScotty")]
[assembly: AssemblyDescription("Retro 8-Bit High-Speed Folder Backup Utility (ZX Spectrum / C64)")]
[assembly: AssemblyCompany("RetroSoft")]
[assembly: AssemblyProduct("BackMeUpScotty")]
[assembly: AssemblyVersion("1.0.0.0")]

static class Program
{
    [STAThread]
    static int Main(string[] args)
    {
        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string mainPy = Path.Combine(exeDir, "main.py");
        if (!File.Exists(mainPy))
        {
            MessageBox.Show("Could not find main.py in:\n" + exeDir, "BackMeUpScotty Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        string argStr = "\"" + mainPy + "\"";
        foreach (string a in args)
        {
            argStr += " \"" + a.Replace("\"", "\\\"") + "\"";
        }

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = "pythonw.exe";
        psi.Arguments = argStr;
        psi.WorkingDirectory = exeDir;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;

        try
        {
            Process.Start(psi);
            return 0;
        }
        catch
        {
            try
            {
                psi.FileName = "python.exe";
                Process.Start(psi);
                return 0;
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to launch Python runtime:\n" + ex.Message, "BackMeUpScotty Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }
    }
}