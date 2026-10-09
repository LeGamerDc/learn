//! 2024 edition 改变了 if let scrutinee 临时值的作用域
//! 预期（2024 edition）：✅  在 2021 edition 下这段会死锁（else 分支里锁还没释放）
use std::sync::RwLock;
pub fn f(l: &RwLock<Option<i32>>) -> i32 {
    if let Some(v) = *l.read().unwrap() { v } else { *l.write().unwrap() = Some(0); 0 }
}
