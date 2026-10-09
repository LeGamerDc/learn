//! MutexGuard 的作用域：临时值活到语句末尾导致的自锁
//! 预期：编译 ✅（但运行时死锁）—— borrow checker 不管死锁
use std::sync::Mutex;
pub fn f(m: &Mutex<Vec<i32>>) -> usize { let n = m.lock().unwrap().len(); n }
