import "../index.css"
import { use, useState } from "react"
import { useRef } from "react"

export default function CopyButton(msgs) {

    const [clicked, updateclick] = useState(0)
     

    return(
    <>
    <button className="copybtn" onClick={()=>{navigator.clipboard.writeText(msgs.msgs["text"]); updateclick(true); setTimeout(() => {updateclick(false)},3000)}}><span>{clicked ? "Copied To Clipboard.":"Copy"}</span></button>
    </>
    )
}