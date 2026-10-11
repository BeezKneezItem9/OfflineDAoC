using System;
using System.Runtime.InteropServices;
using System.Text;
namespace Beez {
 public sealed class NativeSqlite : IDisposable {
  IntPtr db;
  const string Library = "winsqlite3.dll";
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_open_v2(byte[] name, out IntPtr db, int flags, IntPtr vfs);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_close(IntPtr db);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_busy_timeout(IntPtr db, int ms);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern IntPtr sqlite3_errmsg(IntPtr db);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_prepare_v2(IntPtr db, byte[] sql, int count, out IntPtr stmt, IntPtr tail);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_step(IntPtr stmt);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern IntPtr sqlite3_column_text(IntPtr stmt, int col);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_finalize(IntPtr stmt);
  static byte[] Utf8(string s) { return Encoding.UTF8.GetBytes(s + "\0"); }
  static string Text(IntPtr p) {
   if (p == IntPtr.Zero) return null;
   int n=0; while (Marshal.ReadByte(p,n)!=0) n++;
   byte[] b=new byte[n]; Marshal.Copy(p,b,0,n); return Encoding.UTF8.GetString(b);
  }
  void Check(int rc) { if(rc!=0) throw new InvalidOperationException("SQLite: " + Text(sqlite3_errmsg(db))); }
  public NativeSqlite(string path) {
   try { Check(sqlite3_open_v2(Utf8(path),out db,2,IntPtr.Zero)); Check(sqlite3_busy_timeout(db,2500)); }
   catch { Dispose(); throw; }
  }
  public string Scalar(string sql) {
   IntPtr stmt=IntPtr.Zero;
   try {
    Check(sqlite3_prepare_v2(db,Utf8(sql),-1,out stmt,IntPtr.Zero));
    int rc=sqlite3_step(stmt);
    if(rc==100) return Text(sqlite3_column_text(stmt,0));
    if(rc==101) return null;
    Check(rc); return null;
   } finally { if(stmt!=IntPtr.Zero) sqlite3_finalize(stmt); }
  }
  public void Exec(string sql) {
   IntPtr stmt=IntPtr.Zero;
   try { Check(sqlite3_prepare_v2(db,Utf8(sql),-1,out stmt,IntPtr.Zero)); int rc=sqlite3_step(stmt); if(rc!=101) Check(rc); }
   finally { if(stmt!=IntPtr.Zero) sqlite3_finalize(stmt); }
  }
  public void Dispose() { if(db!=IntPtr.Zero) { sqlite3_close(db); db=IntPtr.Zero; } }
 }
}
