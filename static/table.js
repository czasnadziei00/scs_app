async function loadData() {
    try {
        const res = await fetch("cache.json?cache=" + Math.random());
        const data = await res.json();

        const tbody = document.getElementById("table-body");
        tbody.innerHTML = "";

        const entries = Object.entries(data).sort((a, b) => b[1].SCS - a[1].SCS);

        for (const [ticker, d] of entries) {
            const tr = document.createElement("tr");

            // SIGNAL COLOR
            let signalClass = "signal-neutral";
            if (d.Signal === "STRONG BUY") signalClass = "signal-strong";
            else if (d.Signal === "BUY") signalClass = "signal-buy";
            else if (d.Signal === "SELL") signalClass = "signal-sell";

            tr.innerHTML = `
                <td><b>${ticker}</b></td>
                <td>${d.Last.toFixed(2)}</td>
                <td class="${d.SCS > 0 ? "green" : "red"}">${d.SCS}</td>
                <td class="${d.Trend15 === "UP" ? "green" : d.Trend15 === "DOWN" ? "red" : "yellow"}">${d.Trend15}</td>
                <td class="${d.Trend60 === "UP" ? "green" : d.Trend60 === "DOWN" ? "red" : "yellow"}">${d.Trend60}</td>
                <td class="${signalClass}">${d.Signal}</td>
                <td><span class="buyzone">${d.BuyZoneLow} — ${d.BuyZoneHigh}</span></td>
                <td class="${d.TP1 > d.Last ? "tp-green" : "tp-gray"}">${d.TP1}</td>
                <td class="${d.TP2 > d.Last ? "tp-green" : "tp-gray"}">${d.TP2}</td>
                <td class="${d.TP3 > d.Last ? "tp-green" : "tp-gray"}">${d.TP3}</td>
                <td>${d.Time}</td>
            `;

            tbody.appendChild(tr);
        }

        document.getElementById("updated").innerText =
            "Ostatnia aktualizacja: " + new Date().toLocaleTimeString();

    } catch (e) {
        console.log("ERROR loading cache:", e);
    }
}

setInterval(loadData, 5000);
loadData();
