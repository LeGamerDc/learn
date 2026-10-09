//! 从链表收集所有元素的 &mut：借用要"活过"循环的下一轮迭代。
//! 这个形态在 NLL RFC 时代被列为难点，但今天的 NLL 已经能处理——
//! 保留它是为了说明：NLL 本身这些年也一直在改进，"NLL 做不到 X" 的老结论要复核。
//! 实测（1.100.0-nightly）：NLL ✅  Polonius ✅
pub struct List<T> { pub value: T, pub next: Option<Box<List<T>>> }
pub fn to_refs<T>(mut list: &mut List<T>) -> Vec<&mut T> {
    let mut result = vec![];
    loop {
        result.push(&mut list.value);
        if let Some(n) = list.next.as_mut() { list = n; } else { return result; }
    }
}
