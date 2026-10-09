//! 闭包捕获不相交字段（RFC 2229 "disjoint closure capture"，2021 edition 起）
//! 预期：NLL ✅  Polonius ✅（在 2018 edition 下这会失败）
pub struct S { a: String, b: String }
pub fn f(s: &mut S) {
    let mut c = || s.a.push('x');
    // 2021 edition 起闭包只捕获 s.a，所以下面这行不冲突
    c();
    s.b.push('y');
}
