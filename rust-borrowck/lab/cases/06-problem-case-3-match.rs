//! NLL problem case #3：条件控制流跨函数（HashMap get-or-insert），match 版
//! 预期：NLL ❌ E0499  Polonius ✅
use std::collections::HashMap; use std::hash::Hash;
pub fn f<'r, K: Hash + Eq + Copy, V: Default>(map: &'r mut HashMap<K, V>, key: K) -> &'r mut V {
    match map.get_mut(&key) {
        Some(v) => v,
        None => { map.insert(key, V::default()); map.get_mut(&key).unwrap() }
    }
}
