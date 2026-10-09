//! MutexGuard 跨 await：Future 不再是 Send，无法交给多线程 executor
//! 预期：❌ E0277
use std::sync::Mutex;
fn assert_send<T: Send>(_: T) {}
async fn yield_now() {}
async fn bad(m: &Mutex<i32>) { let g = m.lock().unwrap(); yield_now().await; println!("{}", *g); }
pub fn f(m: &'static Mutex<i32>) { assert_send(bad(m)); }
