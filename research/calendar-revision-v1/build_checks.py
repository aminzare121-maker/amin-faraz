"""Compile staged clients, never start app/MT5, sign APK or install."""
import importlib.util,json,pathlib,subprocess,shutil
ROOT=pathlib.Path(__file__).resolve().parent
ORIGINAL=pathlib.Path('C:/Users/Pixel/Documents/Amin-MT5-0.4.1/amin-mt5')
spec=importlib.util.spec_from_file_location('build_helper',ORIGINAL/'scripts/build_local_windows.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
out=ROOT/'build';out.mkdir(exist_ok=True)
shim=out/'Implicit.cs'
shim.write_text('''global using System;
global using System.Collections.Generic;
global using System.Drawing;
global using System.IO;
global using System.Linq;
global using System.Net.Http;
global using System.Threading;
global using System.Threading.Tasks;
global using System.Windows.Forms;
namespace Amin.Owner { internal static class ApplicationConfiguration {
internal static void Initialize() { throw new InvalidOperationException("Compile-only candidate"); }
} }
''',encoding='utf-8')
refs=[p for p in (ORIGINAL/'clients/windows-installed').glob('*.dll') if p.name!='AminOwner.dll' and helper.managed(p)]
refs += [ORIGINAL/('toolchain/webview2/lib/net462/'+n) for n in ('Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll')]
sources=[ROOT/'candidate/windows/ResearchCalendarPanel.cs' if p.name=='ResearchCalendarPanel.cs' else p for p in (ORIGINAL/'clients/windows-native').glob('*.cs')]+[shim]
args=['/nologo','/target:library','/langversion:latest','/nullable:enable','/deterministic+',
      '/out:'+str(out/'CalendarClientCompileOnly.dll'),*['/reference:'+str(p) for p in refs],*[str(p) for p in sources]]
rsp=out/'compile.rsp';rsp.write_text('\n'.join('"'+x+'"' for x in args),encoding='utf-8')
win=subprocess.run(['dotnet',str(ORIGINAL/'toolchain/roslyn-4.11/tasks/netcore/bincore/csc.dll'),'@'+str(rsp)],capture_output=True,text=True)
(ROOT/'windows-compile.txt').write_text(win.stdout+win.stderr,encoding='utf-8')
tools=pathlib.Path('C:/Users/Pixel/Documents/Codex/2026-10-22/zip-chatgpt/work/android_stage/tools')
android=out/'android.jar'
shutil.copyfile(tools/'android_sdk/platforms/android-35/android.jar',android)
java_sources=[ROOT/'candidate/android/DashboardActivity.java' if p.name=='DashboardActivity.java' else p for p in (ORIGINAL/'clients/android/src').rglob('*.java')]
java_sources += list((ORIGINAL/'clients/android/builds/20261028T192840Z/generated').rglob('*.java'))
classes=out/'android-classes';classes.mkdir(exist_ok=True)
javac=subprocess.run([str(tools/'java/jdk-21.0.12.1+1/bin/javac.exe'),'-encoding','UTF-8','-source','8','-target','8','-Xlint:-options','-classpath',str(android),'-d',str(classes),*[str(p) for p in java_sources]],capture_output=True,text=True)
(ROOT/'android-compile.txt').write_text(javac.stdout+javac.stderr,encoding='utf-8')
android_ok=javac.returncode==0 and 'exception has occurred' not in javac.stderr.lower() and (classes/'ir/amin/gold/DashboardActivity.class').is_file()
result={'windows_compile_exit':win.returncode,'android_compile_exit':javac.returncode,'android_compile_verified':android_ok,'app_launched':False,'installed':False,'signed':False,'device_tested':False}
(ROOT/'build-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));print(win.stdout+win.stderr);print(javac.stdout+javac.stderr)
raise SystemExit(bool(win.returncode or not android_ok))
