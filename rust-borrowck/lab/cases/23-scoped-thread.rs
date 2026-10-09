//! 同一件事用 scoped thread：编译器能证明线程在 scope 结束前 join
//! 预期：✅
pub fn f() {
    let v = vec![1, 2, 3];
    std::thread::scope(|s| { s.spawn(|| println!("{:?}", v)); });
}
