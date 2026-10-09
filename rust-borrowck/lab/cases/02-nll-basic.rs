//! NLL 的基本功：借用在最后一次使用后就结束，而非作用域末尾
//! 预期：NLL ✅  Polonius ✅（这在 2015 年的 Rust 1.0 上是编译不过的）
pub fn f() {
    let mut v = vec![1, 2, 3];
    let first = &v[0];
    println!("{}", first);   // first 最后一次使用
    v.push(4);               // 词法生命周期时代这里会报错
}
